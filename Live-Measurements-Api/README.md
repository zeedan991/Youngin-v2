---
title: Youngin AI Backend
emoji: 👕
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
startup_duration_timeout: 10m
---

# Youngin AI Backend

AI-powered body measurement API using MediaPipe and MiDaS depth estimation.

## Features

- 📏 AI body measurements from photos
- 🤖 Gemini-powered chatbot
- 🔒 Secure and privacy-focused

## API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /measurements` - Body measurements
- `POST /chat` - AI chatbot

## Tech Stack

- Flask + Gunicorn
- MediaPipe
- PyTorch + MiDaS
- Google Gemini AI
