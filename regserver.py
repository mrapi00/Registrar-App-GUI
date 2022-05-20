#!/usr/bin/env python

#-----------------------------------------------------------------------
# regserver.py
#-----------------------------------------------------------------------

import argparse
from os import name
from time import process_time
from sys import stderr, exit
from multiprocessing import Process
from socket import socket, SOL_SOCKET, SO_REUSEADDR
from contextlib import closing
from sqlite3 import connect
#-----------------------------------------------------------------------
# Command line
parser = argparse.ArgumentParser(description='Server for the registrar'
+ ' application', allow_abbrev=False)
parser.add_argument('port', help='the port at which the server ' +
'should listen' , type =int)
args = parser.parse_args()
#-----------------------------------------------------------------------

# GLOBALS
DATABASE_URL = 'file:reg.sqlite?mode=ro'

#-----------------------------------------------------------------------
# function which takes in a string field and adds a '/' character before
# every occurence of an '_' or '%' character. Returns the new string.
def put_escapechar(field) :
    ans = ""
    for element in field :
        if not element in ('_', '%'):
            ans += element
        else:
            ans += "\\" + element

    return ans
#-----------------------------------------------------------------------

# create corresponding fields restrictions if exists
def create_fields(area, dept, num, title) :
    create = ''
    tuple_fields = []
    if area != '' :
        create += "AND area LIKE ? "
        tuple_fields.append("%" + put_escapechar(area) + "%")
    if dept != '' :
        create += "AND dept LIKE ? "
        tuple_fields.append("%" + put_escapechar(dept) + "%")
    if num != '' :
        create += "AND coursenum LIKE ? "
        tuple_fields.append("%" + put_escapechar(num) + "%")
    if title != '' :
        create += "AND title LIKE ? "
        tuple_fields.append("%" + put_escapechar(title) + "%")
    return create, tuple_fields
#-----------------------------------------------------------------------

# create SQL statement to retrieve necessary fields
def create_sql(create) :
    stmt_str = "SELECT classid, dept, coursenum, area, "
    stmt_str += "title FROM classes, courses, "
    stmt_str += "crosslistings WHERE classes.courseid "
    stmt_str += "= courses.courseid AND courses.courseid = "
    stmt_str += "crosslistings.courseid "
    if create != "" :
        stmt_str += create
        stmt_str += " ESCAPE '\\' "
    stmt_str += "ORDER BY dept ASC, coursenum ASC, "
    stmt_str += "classid ASC"
    return stmt_str
#-----------------------------------------------------------------------
# adds the class fields to SQL statement
def class_fields() :
    stmt_str = "SELECT courseid, days, starttime, endtime, "
    stmt_str += "bldg, roomnum FROM classes "
    stmt_str += "WHERE classid = ?"
    return stmt_str

# adds the crosslisting fields to SQL statement
def crosslisting_fields(courseid) :
    stmt_str = "SELECT dept, coursenum "
    stmt_str += "FROM crosslistings WHERE courseid = "
    stmt_str += courseid
    stmt_str += " ORDER BY dept ASC, coursenum ASC"
    return stmt_str

# adds the course fields to SQL statement
def courses_fields(courseid) :
    stmt_str = "SELECT area, title, descrip, prereqs "
    stmt_str += "FROM courses WHERE courseid = "
    stmt_str += courseid
    return stmt_str

# adds the professor fields to SQL statement
def prof_fields(courseid) :
    stmt_str = "SELECT profname "
    stmt_str += "FROM profs, coursesprofs WHERE courseid = "
    stmt_str += courseid
    stmt_str += " AND coursesprofs.profid == profs.profid"
    stmt_str += " ORDER BY profname ASC"
    return stmt_str

#----------------------------------------------------------------------
# helper function to write out area, title, descrip, and pre-reqs
def getdetailhelper(out_flo, row) :
    out_flo.write("Area: " + row[0] + '\n')
    out_flo.write('\n')

    out_flo.write("Title: " + row[1]+ '\n')
    out_flo.write('\n')
    out_flo.write("Description: " + row[2] + '\n')
    out_flo.write('\n')

    out_flo.write("Prerequisites: " + row[3] + '\n')
    out_flo.write('\n')

# executes the "get_detail" command from client
def getdetails(sock, in_flo) :
    classid = in_flo.readline().strip()
    try:
        with connect (DATABASE_URL, isolation_level=None,
        uri = True) as connection :
            with closing(connection.cursor()) as cursor :
                # choose initial fields from classes to display
                out_flo = sock.makefile(mode='w', encoding='utf-8')
                stmt_str = class_fields()
                cursor.execute(stmt_str, [classid])

                row = cursor.fetchone()

                # for non-existing classid error handling from server
                # side
                if row is None:
                    message = "The classid " + classid
                    message += " does not exist"
                    print(message, file=stderr)
                    out_flo.write("NO CLASSID\n")
                    out_flo.flush()
                    return
                out_flo.write("CLASSID EXISTS\n")
                out_flo.flush()

                courseid = str(row[0])
                out_flo.write("Course Id: " + courseid + '\n')
                out_flo.write('\n')
                out_flo.write("Days: " + row[1] + '\n')
                out_flo.write("Start time: " + row[2] + '\n')
                out_flo.write("End time: " + row[3] + '\n')
                out_flo.write("Building: " + row[4] + '\n')
                out_flo.write("Room: " + row[5] + '\n')
                out_flo.write('\n')

                # choose corresponding fields from crosslisting
                stmt_str = crosslisting_fields(courseid)
                cursor.execute(stmt_str)

                row = cursor.fetchone()
                while row is not None:
                    out_flo.write("Dept and Number: " + row[0] + " "
                    + row[1] + '\n')
                    row = cursor.fetchone()
                out_flo.write('\n')

                # choose corresponding fields from courses to display
                stmt_str = courses_fields(courseid)
                cursor.execute(stmt_str)

                row = cursor.fetchone()
                getdetailhelper(out_flo, row)
                # choose corresponding fields from profs to display
                stmt_str = prof_fields(courseid)
                cursor.execute(stmt_str)

                row = cursor.fetchone()
                while row is not None:
                    out_flo.write("Professor: " + row[0] + '\n')
                    row = cursor.fetchone()
                out_flo.flush()
    except Exception as ex:
        print(ex, file=stderr)
        out_flo.write('System Error\n')
#----------------------------------------------------------------------
# executes the "get_overview" command from client
def submit(sock, in_flo) :
    dept = in_flo.readline().strip('\n')
    num = in_flo.readline().strip('\n')
    area = in_flo.readline().strip('\n')
    title = in_flo.readline().strip('\n')

    out_flo = sock.makefile(mode='w', encoding='utf-8')
    # create blank list to populate for SQL prepared statements
    tuple_fields = []
    create = ""
    create, tuple_fields = create_fields(area, dept, num, title)
    try:
        with connect (DATABASE_URL, isolation_level=None,
        uri = True) as connection :
            with closing(connection.cursor()) as cursor :
                # SQL statement to select corresponding fields
                stmt_str = create_sql(create)
                cursor.execute(stmt_str, tuple_fields)

                row = cursor.fetchone()
                # print with formatting
                while row is not None:
                    # ClassID
                    out_flo.write("%5s " % (row[0]))
                    # Dept
                    out_flo.write("%3s " % (row[1]))
                    # Course Num
                    out_flo.write("%4s " % (row[2]))
                    # Area
                    out_flo.write("%3s " % (row[3]))
                    #Title
                    out_flo.write("%-40s " % (row[4]))
                    out_flo.write('\n')
                    out_flo.flush()
                    row = cursor.fetchone()
    except Exception as ex:
        print(ex, file=stderr)
        out_flo.write('System Error\n')

# handles command received from client
def handle_client(sock):
    in_flo = sock.makefile(mode = 'r', encoding = 'utf-8')
    command = in_flo.readline().strip()
    if command == 'submit' :
        # print('get_overview')
        submit(sock, in_flo)
    elif command == 'details':
        # print('get_detail')
        getdetails(sock, in_flo)
    sock.close()
    print('Closed socket in child process')
    print('Exiting child process')
#-----------------------------------------------------------------------
# creates socket to communicate with a client
def main():
    try:
        port = args.port
        server_sock = socket()
        print('Opened server socket')
        if name != 'nt' :
            server_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server_sock.bind(('', port))
        print('Bound server socket to port')
        server_sock.listen()
        print('Listening')

        while True:
            sock, _ = server_sock.accept()
            with sock:
                print('Accepted connection, opened socket')
                print('Received command: ', end = "")
                process = Process(target=handle_client,
                args=[sock])
                process.start()
            print('Closed socket in parent process')
    except Exception as ex:
        print(ex, file=stderr)
        exit(1)

if __name__ == '__main__':
    main()
