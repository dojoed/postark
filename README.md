# PostArk

Preserving history, one postcard at a time.

## Overview

PostArk is a Streamlit web application that analyzes and preserves the historical significance of old postcards. Upload vintage postcards and the app will extract details, analyze stamps, research individuals, and generate historical narratives.

## Features

- **Postcard Analysis**: Extract sender, receiver, location, date, and message from postcard images
- **Stamp Analysis**: Identify and analyze postage stamps
- **Historical Research**: Search for historical information about people mentioned on postcards
- **Narrative Generation**: Generate historically grounded stories based on postcard content

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/dojoed/postark.git
   cd postark
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY and SERPAPI_API_KEY to .env
   ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Streamlit Cloud.

## Technologies

- Streamlit - Web framework
- OpenAI GPT-4 Vision - Image analysis and narrative generation
- SerpAPI - Web search for historical research
- Python Imaging Library (PIL) - Image processing
