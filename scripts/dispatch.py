#!/usr/bin/env python3
"""Operations user's client. Feed task JSON on stdin or --task-file, never shell.
Each task_id is durable/idempotent; after an ambiguous timeout use action=status.
"""
import argparse, json, socket, sys
from worker_bridge import validate_request,MAX_REQUEST,MAX_RESULT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['planning','development'],required=True);parser.add_argument('--task-file');a=parser.parse_args()
    data=open(a.task_file).read() if a.task_file else sys.stdin.read(MAX_REQUEST+1)
    if len(data.encode())>MAX_REQUEST: raise ValueError('request too large')
    req=validate_request(json.loads(data),a.profile)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(730);conn.connect('/run/oracle-ai-stack/'+a.profile+'.sock')
        conn.sendall(json.dumps(req).encode());conn.shutdown(socket.SHUT_WR)
        output=bytearray()
        while True:
            part=conn.recv(65536)
            if not part:break
            output.extend(part)
            if len(output)>MAX_RESULT+8192: raise ValueError('response too large')
    print(json.dumps(json.loads(output),ensure_ascii=False))
if __name__=='__main__': main()
