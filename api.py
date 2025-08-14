import base64
import json
import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from groq import Groq

from config import logger, settings

client = Groq(api_key=settings.GROQ_API_KEY)


def find_url(text):
    regex = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+"
    return re.findall(regex, text)


def send_yandex_api(link):
    endpoint = "https://300.ya.ru/api/sharing-url"
    response = requests.post(
        endpoint,
        json={"article_url": f"{link}"},
        headers={"Authorization": f"OAuth {settings.YA_ID}"},
    )
    return response.json().get("sharing_url")


def read_url(target):
    final_url = send_yandex_api(target)
    if final_url:
        logger.info(f"Получен ответ от YandexGPT: {final_url}")
        response = requests.get(final_url)
        soup = BeautifulSoup(response.content, "html.parser")
        og_title_tag = soup.find("meta", attrs={"property": "og:title"})
        if og_title_tag:
            title = og_title_tag["content"]
        og_description_tag = soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if og_description_tag:
            description = og_description_tag["content"]
        return title + "\n\n" + description
    else:
        logger.warning("Ошибка в ответе от YandexGPT")
        return None


def send_conversation(content):
    dt = datetime.now()
    time_name = str(datetime.timestamp(dt)).replace(".", "")
    url = f"https://blog.antoncp.nl/create_page/{time_name}"
    username = settings.API_LOGIN
    password = settings.API_PAS
    credentials = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {credentials}"}
    response = requests.post(
        url, data=content.encode("utf-8"), headers=headers
    )
    if response.json().get("status") == "created":
        link = response.json().get("link")
        final_url = send_yandex_api(link)
        requests.delete(url, headers=headers)
        if final_url:
            response = requests.get(final_url)
            soup = BeautifulSoup(response.content, "html.parser")
            og_description_tag = soup.find(
                "meta", attrs={"property": "og:description"}
            )
            if og_description_tag:
                description = og_description_tag["content"]
            return description


def writing_message(message):
    data = {
        "timestamp": message.date,
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "user_first_name": message.from_user.first_name,
        "user_last_name": message.from_user.last_name,
        "text": message.text,
    }
    url = "http://localhost/save_message/"
    username = settings.API_LOGIN
    password = settings.API_PAS
    credentials = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {credentials}"}
    try:
        requests.post(
            url, data=json.dumps(data), headers=headers, timeout=(1, None)
        )
    except Exception:
        logging.info(f"ОШИБКА ЗАПИСИ: {message.text[:45]}...")


def summ_with_groq(messages):
    message = [{"role": "user", "content": f"{settings.PROMPT}{messages}"}]
    response = client.chat.completions.create(
        model="llama3-8b-8192", messages=message, temperature=0
    )
    return response


def scrape_linkedin_jobs():
    """
    Scrapes LinkedIn for IT jobs in The Netherlands.
    Returns list of job dictionaries with title, company, location, and link.
    Note: LinkedIn actively blocks scrapers - this may need regular
    maintenance.
    """

    # IT-related keywords for filtering
    it_keywords = [
        'software engineer', 'software developer', 'python developer',
        'java developer',
        'javascript developer', 'react developer',
        'frontend developer', 'backend developer',
        'full stack developer', 'web developer', 'mobile developer',
        'ios developer',
        'android developer', 'devops engineer', 'system administrator',
        'data scientist',
        'data analyst', 'machine learning engineer', 'product designer',
        'ui designer',
        'ux designer', 'product manager', 'technical lead',
        'engineering manager',
        'qa engineer', 'test engineer', 'cybersecurity',
        'cloud engineer', 'architect'
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;'
                  'q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        # LinkedIn job search URL for Netherlands with IT keywords
        # Using multiple searches to increase IT job results
        search_terms = [
            "software%20engineer",
            "software%20developer",
            "frontend%20developer",
            "backend%20developer",
            "python%20developer",
            "javascript%20developer"
        ]

        all_jobs = []

        for term in search_terms[:2]:  # Use first 2 terms to avoid
                                        # too many requests
            url = (f"https://www.linkedin.com/jobs/search/"
                   f"?keywords={term}&location=Netherlands&sortBy=DD")

            logger.info(
                f"Searching LinkedIn for: {term.replace('%20', ' ')}"
            )

            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Look for job cards (LinkedIn's structure may change)
                    job_cards = soup.find_all('div', class_='base-card')
                    if not job_cards:
                        job_cards = soup.find_all(
                        'div', {'data-entity-urn': True}
                    )

                    for card in job_cards[:15]:  # Process first 15 jobs
                                              # from each search
                        try:
                            # Extract job title
                            title_elem = (
                            card.find('h3') or
                            card.find('a', class_='base-card__full-link')
                        )
                            title = (
                            title_elem.get_text(strip=True)
                            if title_elem else "Unknown Title"
                        )

                            # Extract company name
                            company_elem = (
                            card.find('a', class_='hidden-nested-link') or
                            card.find('h4')
                        )
                            company = (
                            company_elem.get_text(strip=True)
                            if company_elem else "Unknown Company"
                        )

                            # Extract location
                            location_elem = card.find(
                            'span', class_='job-search-card__location'
                        )
                            location = (
                            location_elem.get_text(strip=True)
                            if location_elem else "Netherlands"
                        )

                            # Extract job link
                            link_elem = card.find(
                            'a', class_='base-card__full-link'
                        )
                            link = (
                            link_elem.get('href') if link_elem else "#"
                        )

                            # Since we're searching with IT terms, most
                        # results should be IT-related
                            # But still filter to be sure
                            title_lower = title.lower()
                            if any(
                            keyword in title_lower for keyword in it_keywords
                        ):
                                job_data = {
                                    'title': title,
                                    'company': company,
                                    'location': location,
                                    'link': (
                                f"https://linkedin.com{link}"
                                if link.startswith('/')
                                else link
                            )
                                }

                                # Avoid duplicates by checking if job
                            # already exists
                                if not any(
                                j['title'] == title and j['company'] == company
                                for j in all_jobs
                            ):
                                    all_jobs.append(job_data)

                        except Exception as e:
                            logger.warning(f"Error parsing job card: {e}")
                            continue

                elif response.status_code == 429:
                    logger.warning("LinkedIn rate limiting detected (429)")
                    break  # Stop searching if rate limited
                else:
                    logger.warning(
                        f"LinkedIn returned status code: "
                        f"{response.status_code} for term: {term}"
                    )

                # Add small delay between requests to be polite
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {term}: {e}")
                continue

        # Sort by relevance and limit to 10
        jobs = all_jobs[:10]
        logger.info(f"Successfully scraped {len(jobs)} IT jobs from LinkedIn")
        return jobs

    except Exception as e:
        logger.error(f"Unexpected error during LinkedIn scraping: {e}")
        return []


def format_jobs_message(jobs):
    """Format job list into a readable Telegram message."""
    if not jobs:
        return (
            "🔍 Sorry, no IT jobs found in The Netherlands at the moment. "
            "LinkedIn might be blocking requests or there are no new postings."
        )

    message = "🇳🇱 **Latest IT Jobs in The Netherlands:**\n\n"

    for i, job in enumerate(jobs, 1):
        message += f"**{i}. {job['title']}**\n"
        message += f"🏢 {job['company']}\n"
        message += f"📍 {job['location']}\n"
        message += f"🔗 [Apply here]({job['link']})\n\n"

    message += (
        "⚠️ *Note: LinkedIn actively blocks scrapers. If no jobs appear, "
        "try again later.*"
    )
    return message
