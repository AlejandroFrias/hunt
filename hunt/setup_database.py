import settings
import sqlite3


def main():
    conn = sqlite3.connect(settings.DATABASE)
    with open('create-tables') as ct:
        for sql_statement in ct.read().splitlines():
            conn.execute(sql_statement)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
