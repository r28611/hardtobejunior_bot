def choose_noun_case(score, word='балл'):
    ending = ''
    remainder = score % 10
    if (remainder >= 5 or remainder == 0 or
       (score > 10 and 10 < int(str(score)[-2:]) < 20)):
        ending = 'ов'
    elif 1 < remainder < 5:
        ending = 'a'
    return f'{score} {word}{ending}'
