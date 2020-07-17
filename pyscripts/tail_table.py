#!/usr/bin/env python3

import argparse
import sys
import psycopg2

def main(table):

    dsn = 'postgresql://localhost:6875/materialize?sslmode=disable'
    conn = psycopg2.connect(dsn)

    with conn.cursor() as cursor:
        cursor.copy_expert("TAIL {}".format(table), sys.stdout)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('table', help='Name of table to tail')
    args = parser.parse_args()
    main(args.table)
