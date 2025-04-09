TENDENCY_SCORE_TABLE = [[1, 3, 5],
                        [1, 2, 3, 4, 5],
                        6, [1, 3, 5],
                        3, [1, 3, 5],
                        1, [1, 3, 5],
                        0,
                        [1, 3, 5],
                        [1, 3, 4, 5],
                        [1, 2, 3, 4],
                        0,
                        0,
                        0]

LENGTH_TABLE = {
    2: 4,
    3: 3,
    4: 6,
    5: 3,
    6: 3,
    7: 3
}


def validate_score(data):
    score_table = TENDENCY_SCORE_TABLE
    score = 0
    section = 0
    errors = {}
    results = []
    first = False

    for idx, value in enumerate(data):
        try:
            sc = score_table[idx]

            if idx in [2, 3, 4, 5, 6, 7]:
                if value \
                        and section == 0 \
                        and idx in [2, 4, 6] \
                        and list(filter(lambda x: x > 0, value)):

                    results.append('|'.join(sorted([str(v) for v in value])))
                    section = (sc + score_table[idx + 1][data[idx + 1] - 1])

                    # print(idx, sc, score_table[idx + 1][data[idx + 1] - 1])

                    score += section
                else:
                    length = LENGTH_TABLE.get(idx)
                    if isinstance(value, int):
                        if not first:
                            length -= length
                            first = True
                        results.append(value + length if value else value)
                    else:
                        results.append('|'.join([str(v + length) for v in sorted(value)] if bool(value) else "0"))
                    continue
            elif idx == 8 and value:
                results.append(value)
                score -= section
            else:
                if isinstance(sc, list):
                    if value - 1 >= 0:
                        score += sc[value - 1]
                        results.append(value)
                    else:
                        raise IndexError('list index out of range')
                else:
                    results.append(value)

        except IndexError as e:
            if len(score_table) > idx:
                errors[idx] = '{} - allow range 1 to {}'.format(str(e), len(score_table[idx]))
            else:
                errors[idx] = e
        except Exception as e:
            errors[idx] = e

    if errors:
        print(errors)

    return score, results


def get_risk_type(score):
    if score <= 10:
        return 0
    elif 11 <= score <= 15:
        return 1
    elif 16 <= score <= 20:
        return 2
    elif 21 <= score <= 25:
        return 3
    elif 26 <= score:
        return 4
