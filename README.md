# MyPick — A Data-Driven KBO Fantasy Sports & Player Valuation Platform

MyPick is a full-stack sports analytics platform that transforms raw KBO baseball records into fantasy scores, dynamic player valuations, user rankings, and point-based prediction experiences.

The project was built to explore how structured sports data can be converted into an interactive product that helps fans understand player value, compare performance, build fantasy teams, and engage with daily KBO games.

---

## Live Demo

- Live Website: https://mypickkbo.com
- Project Type: Full-stack sports analytics web application
- Domain: Sports analytics, fantasy sports, player valuation, data products
- Status: Portfolio-safe repository version

> This repository does not include production database files, environment secrets, logs, backups, or private deployment credentials.

---

## Project Overview

Baseball produces a large amount of structured statistical data, but raw game records and traditional stat tables are often difficult for casual fans to interpret.

MyPick addresses this gap by converting KBO records into a user-facing fantasy sports experience. Instead of simply displaying historical records, the platform reinterprets player performance through custom scoring, dynamic pricing, ranking, team-building, and prediction systems.

The goal is to make player value easier to understand and make daily KBO games more interactive for fans.

---

## Problem Statement

Most sports data platforms focus on displaying statistics, schedules, and rankings. While useful, these formats often leave users with questions such as:

- Which players are actually valuable right now?
- How can recent performance be compared across different roles?
- How can raw baseball records become an interactive fan experience?
- How can a platform combine sports analytics, user participation, and live operations?

MyPick was designed as a data product that turns raw KBO records into interpretable fantasy scores, player prices, rankings, and prediction-based interactions.

---

## Key Features

### 1. KBO Data Pipeline

MyPick processes KBO game information through a daily data pipeline.

Core pipeline responsibilities include:

- Collecting daily KBO game records
- Storing raw batter and pitcher statistics
- Separating batter, starting pitcher, and bullpen pitcher logic
- Calculating fantasy daily scores
- Updating player totals and rankings
- Updating dynamic player prices
- Refreshing fantasy team rankings
- Preparing game prediction markets
- Running validation checks for data consistency

### 2. Fantasy Scoring System

The platform converts raw baseball performance into fantasy points.

The scoring system is designed to:

- Evaluate batters, starting pitchers, and bullpen pitchers differently
- Reflect role-specific performance patterns
- Support daily player scores
- Aggregate player scores into fantasy team scores
- Apply captain-based scoring logic
- Support user rankings based on team performance

This turns traditional baseball records into a more intuitive performance layer for users.

### 3. Dynamic Player Pricing Model

MyPick includes a custom player valuation system that updates player prices based on performance and role.

The pricing model is designed to:

- Represent player value as an interpretable number
- React to recent performance
- Separate valuation logic by player type
- Reduce unstable price movement
- Support fantasy team construction under budget constraints

This creates a market-like layer where users can evaluate player value, roster strategy, and team-building decisions.

### 4. Fantasy Team Management

Users can build fantasy teams using KBO players.

Team management features include:

- Budget-based roster construction
- Position-aware roster slots
- Batter and pitcher role separation
- Captain selection
- Team score aggregation
- User ranking comparison
- Team performance history

The team system connects individual player analytics to user-level competition.

### 5. User Rankings

MyPick tracks and ranks users based on fantasy team performance.

Ranking features include:

- Daily team rankings
- Monthly team rankings
- Season-level user performance
- Team score aggregation
- User comparison through fantasy points and portfolio-style performance

This turns the platform from a static analytics dashboard into a competitive fantasy sports experience.

### 6. Point-Based Prediction System

MyPick includes a point-based prediction and betting-style system for KBO games.

The prediction system supports:

- Game prediction markets
- User point staking
- Bet tracking
- Market settlement
- Payout calculation
- User betting history
- Prediction performance feedback

This feature was designed as a structured engagement layer rather than a real-money gambling system.

---

## System Architecture

```text
KBO Game Data
     ↓
Data Collection / Sync Scripts
     ↓
SQLite Database
     ↓
Fantasy Scoring Engine
     ↓
Dynamic Player Pricing Engine
     ↓
Fantasy Team / Ranking Logic
     ↓
Prediction Market / Settlement Logic
     ↓
Flask Web Application
     ↓
Gunicorn + Nginx + HTTPS
     ↓
User-Facing Web Platform
```

---

## Data Pipeline

The daily update pipeline powers the platform by transforming raw game records into user-facing analytics.

```text
1. Fetch or sync daily KBO game data
2. Store raw batter and pitcher records
3. Calculate fantasy daily scores
4. Aggregate player totals
5. Aggregate fantasy team scores
6. Update dynamic player prices
7. Update rankings and prediction markets
8. Run validation and consistency checks
9. Serve updated results through the web application
```

The pipeline is designed to support automated daily operations while maintaining data quality across game records, player scores, price updates, team rankings, and prediction settlement.

---

## Core Analytics Logic

### Fantasy Scoring Model

The fantasy scoring model transforms raw KBO game records into fantasy points.

Rather than treating all players the same, the model separates players by role:

- Batters
- Starting pitchers
- Bullpen pitchers

This allows the scoring system to better reflect how different types of players contribute to the game.

### Dynamic Player Pricing Model

The pricing model converts player performance into a dynamic valuation layer.

The goal is not simply to rank players by total points, but to create a more interpretable player value system that can support fantasy team-building decisions.

The pricing model considers:

- Player role
- Recent performance
- Fantasy score movement
- Market stability
- Roster strategy

### Prediction Market Logic

The prediction system allows users to participate in daily KBO games using points.

It includes logic for:

- Market creation
- Bet placement
- Bet settlement
- Payout calculation
- User betting history
- Ledger-style point tracking

This system adds an engagement layer to the analytics platform.

---

## Tech Stack

| Area | Technologies |
|---|---|
| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, Jinja Templates, CSS, JavaScript |
| Data Processing | Python scripts |
| Scheduling | systemd service / timer |
| Deployment | AWS Lightsail, Ubuntu, Gunicorn, Nginx |
| Security / Configuration | Environment variables, production-safe config, HTTPS |
| SEO | sitemap.xml, robots.txt, Google Search Console, Naver Webmaster Tools |

---

## Repository Structure

```text
.
├── app.py
├── db.py
├── betting.py
├── scoring.py
├── scheduler.py
├── sync_db.py
├── scraper.py
├── update_market_prices_v3.py
├── calculate_team_daily_scores.py
├── templates/
├── static/
├── docs/
├── deploy/
├── sample_data/
├── screenshots/
├── tests/
├── README.md
├── CHANGELOG.md
└── .gitignore
```

---

## Documentation

Detailed project documentation is organized in the `docs/` directory.

Current and planned documentation topics include:

- Problem statement
- Market context
- Data pipeline
- Fantasy scoring model
- Dynamic pricing model
- Prediction system
- Validation checks
- Deployment
- Roadmap
- Security and privacy

Planned documentation structure:

```text
docs/
├── 01_problem_statement.md
├── 02_market_context.md
├── 03_product_strategy.md
├── 04_data_pipeline.md
├── 05_scoring_model.md
├── 06_pricing_model.md
├── 07_prediction_system.md
├── 08_database_schema.md
├── 09_validation_checks.md
├── 10_deployment.md
├── 11_security_and_privacy.md
└── 12_roadmap.md
```

---

## Screenshots

Screenshots will be added after the portfolio-safe visual review.

Planned screenshot set:

```text
screenshots/
├── 01_center_page.png
├── 02_player_rankings.png
├── 03_player_detail.png
├── 04_team_edit.png
├── 05_my_team.png
├── 06_user_rankings.png
├── 07_prediction_page.png
└── 08_mobile_view.png
```

Example sections to be added:

### Center Dashboard

![Center Dashboard](screenshots/01_center_page.png)

### Player Rankings

![Player Rankings](screenshots/02_player_rankings.png)

### Fantasy Team Management

![Fantasy Team Management](screenshots/04_team_edit.png)

### Prediction System

![Prediction System](screenshots/07_prediction_page.png)

---

## Sample Data

Production database files are not included in this repository.

A small anonymized sample dataset will be added for portfolio demonstration purposes.

Planned sample data structure:

```text
sample_data/
├── sample_games.csv
├── sample_batter_stats.csv
├── sample_pitcher_stats.csv
├── sample_fantasy_scores.csv
├── sample_player_prices.csv
└── README.md
```

The sample data will be simplified and anonymized. It will not include production database files, user-sensitive data, secrets, logs, or operational backups.

---

## Validation and Data Quality

MyPick includes validation checks to reduce the risk of inconsistent updates.

Validation areas include:

- Database integrity checks
- Missing game data detection
- Missing fantasy score detection
- Player price consistency checks
- Position eligibility checks
- Roster budget validation
- Team score aggregation checks
- Betting market settlement checks

These checks are important because the platform depends on multiple connected systems: raw records, fantasy scores, player prices, rosters, rankings, and prediction markets.

---

## Deployment

MyPick is deployed as a production web application.

Deployment components include:

- AWS Lightsail
- Ubuntu
- Gunicorn
- Nginx reverse proxy
- HTTPS with Certbot
- systemd web service
- systemd daily update timer

The production deployment supports automated daily updates and public web access through a custom domain.

Sensitive production files are excluded from this repository.

---

## Security and Privacy Notice

This repository is a portfolio-safe version of the project.

It does not include:

- Production database files
- `.env.production`
- API keys
- Secret keys
- Private server credentials
- Server logs
- Backups
- User-sensitive data
- SSL keys or certificate files
- SSH keys or `.pem` files

Example environment files may be included only with placeholder values.

---

## Roadmap

Planned improvements include:

- Add portfolio-safe screenshots
- Add anonymized sample datasets
- Expand documentation for the scoring and pricing models
- Add database schema documentation
- Add more automated tests
- Improve data validation reports
- Build a GitHub Pages case study site
- Add more product analytics and user engagement metrics
- Explore more advanced player valuation models

---

## Korean Summary

MyPick은 KBO 경기 기록을 단순히 보여주는 사이트가 아니라, 복잡한 야구 데이터를 자체 판타지 점수, 동적 선수 가격, 유저 랭킹, 포인트 기반 승부예측 시스템으로 변환하는 데이터 기반 스포츠 분석 플랫폼입니다.

이 프로젝트는 데이터 수집, 점수화 모델, 선수 가치 평가, 사용자 랭킹, 예측 시스템, 자동화된 운영 파이프라인, 실제 웹 배포까지 포함한 풀스택 데이터 프로덕트입니다.

---

## Author

Jiho Choi  
Data Analytics Student  
Interested in sports analytics, data products, full-stack analytics platforms, and applied data systems.
