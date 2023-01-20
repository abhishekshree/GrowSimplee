#!/bin/bash

# echo "Check if southern-zone-latest.osrm.* exists in osrm directory"
if ls osrm/southern-zone-latest.osrm.* 1> /dev/null 2>&1; then
    echo "Files exist. Running docker-compose"
    docker-compose up -d
    exit 0
else
    echo "Files does not exist."

    echo "Downloading data"
    mkdir -p osrm/
    wget -O osrm/southern-zone-latest.osm.pbf https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf
    echo "Download complete"
    
    echo "Running OSRM"
    docker run -t -v "${PWD}/osrm:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/southern-zone-latest.osm.pbf
    echo "Partitioning"
    docker run -t -v "${PWD}/osrm:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/southern-zone-latest.osrm
    echo "Customizing"
    docker run -t -v "${PWD}/osrm:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/southern-zone-latest.osrm

    echo "Running docker-compose"
    docker-compose up -d
fi
