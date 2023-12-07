#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export ROOT_DIR=${SCRIPT_DIR}/..
export eval $(cat ${ROOT_DIR}/.env.development | grep -v '^#' | grep -v '^\s*$' | sed 's/\${\([^}]*\)}/\$\1/g' | xargs)
eval export eval $(cat ${ROOT_DIR}/.env.development | grep -v '^#' | grep -v '^\s*$' | sed 's/\${\([^}]*\)}/\$\1/g' | xargs)

