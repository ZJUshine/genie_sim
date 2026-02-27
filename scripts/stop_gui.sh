#!/bin/bash

CONTAINER_NAME="genie_sim_benchmark"

if docker ps -q -f name="^${CONTAINER_NAME}$" | grep -q .; then
    echo "Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME"
    echo "Container $CONTAINER_NAME stopped."
else
    echo "Container $CONTAINER_NAME is not running."
fi
