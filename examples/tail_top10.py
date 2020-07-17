#!/usr/bin/env python3

import sys
import psycopg2

def main():

    dsn = 'postgresql://localhost:6875/materialize?sslmode=disable'
    conn = psycopg2.connect(dsn)

    with conn.cursor() as cursor:
        cursor.copy_expert("TAIL top10", sys.stdout)

if __name__ == '__main__':
    main()
