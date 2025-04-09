import sys


def replace(filename, username, password):
    with open(filename, 'r') as f:
        req = f.read()
    req = req.replace('git+https://', f'git+https://{username}:{password}@')
    with open(filename, 'w') as f:
        f.write(req)


if __name__ == '__main__':
    filename = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    replace(filename, username, password)
