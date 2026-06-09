# Deployment

MyPick is deployed as a production web application using a Flask backend behind Gunicorn and Nginx.

## Production Architecture

- Cloud server: AWS Lightsail
- Operating system: Ubuntu
- Web server: Nginx
- Application server: Gunicorn
- Backend framework: Flask
- Database: SQLite
- Automation: systemd service and timer
- HTTPS: Let's Encrypt / Certbot

## Runtime Structure

The production application is separated into two major processes:

1. Web application service  
   Serves the Flask application through Gunicorn and Nginx.

2. Daily data update service  
   Runs the data pipeline on a schedule to collect game records, calculate fantasy scores, update player prices, update team rankings, and process prediction settlements.

## Security and Privacy

The production database, real environment file, secret keys, private user data, logs, backups, and server keys are intentionally excluded from this public portfolio repository.

## Portfolio Scope

This repository focuses on demonstrating the project architecture, code structure, data pipeline, scoring logic, pricing model, and deployment approach without exposing private production data.
