# Hub Management | Grow Simplee

This is a part of the submission for inter IIT Tech Meet 11.0 for the problem statement Route Planning for Optimized On Time Delivery by [Grow Simplee](https://interiit-tech.org/images/ps/High_GS.pdf)

## Steps to Run

1. Clone the repository.
2. Run `git submodule update --recursive --remote` to get the latest version of the frontend submodule.
3. Run `./run.sh` to start the backend servers and the frontend.

## Description

The backend consists of two microservices, one with all the core and business logic, and a standalone OSRM server for faster map related queries. The frontend is a React app that uses the backend to get the data and display it.

The script `run.sh` starts all the three services and takes care of the dependencies. 

The backend is written in Python and uses Flask as the web framework. The frontend is written in React and uses the Tomtom API for the map.

## Demo

[![Demo](https://img.youtube.com/vi/iXQXTKJidzA/0.jpg)](https://www.youtube.com/watch?v=iXQXTKJidzA)
