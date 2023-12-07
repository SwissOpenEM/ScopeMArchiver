#!/bin/bash

usage () {
  echo "Usage: $0 [-e envfile] filename"
  exit 1
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

filename=""
envfile="$SCRIPT_DIR/.env"
while [[ $# -gt 0 ]]; do
  case $1 in
    -e|--envfile)
      envfile="$2"
      shift 
      shift 
      ;;
    -*|--*)
      usage
      ;;
    *)
      filename="$1" 
      shift 
      ;;
  esac
done

if [ "$filename" = "" ]; then
    usage
fi

export $(cat $envfile | sed 's/#.*//' | grep -v '^\s*$' | xargs)

curl "http://localhost:$PORT/delete/$filename"

exit 0
