#!/bin/bash

usage () {
  echo "Usage: $0 [-e envfile] filename"
  exit 1
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

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
      shift 
      ;;
  esac
done

export $(cat $envfile | sed 's/#.*//' | grep -v '^\s*$' | xargs)

curl "http://localhost:$PORT/exit"

exit 0
