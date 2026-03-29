# PostArk Deployment Guide

Your Streamlit app is ready to deploy to Streamlit Cloud! Follow these steps:

## 1. Push to GitHub
```bash
git add .
git commit -m "Initial build - ready for deployment"
git push origin main
```

## 2. Deploy to Streamlit Cloud
1. Go to https://streamlit.io/cloud
2. Click "New app"
3. Connect your GitHub account
4. Select this repository and set:
   - **Repository:** your-username/ai-agents
   - **Branch:** main
   - **Main file path:** app.py

## 3. Set Environment Variables
After deployment, in Streamlit Cloud:
1. Click on the app menu (⋮) → Settings
2. Go to "Secrets"
3. Add these environment variables:
   ```
   OPENAI_API_KEY = your_openai_api_key_here
   SERPAPI_API_KEY = your_serpapi_api_key_here
   ```

## 4. View Your App
The app will be live at: `https://your-username-ai-agents.streamlit.app`

---

**Required Files:**
- ✅ requirements.txt - Created
- ✅ .streamlit/config.toml - Created  
- ✅ .gitignore - Created
- ✅ app.py - Ready
- ✅ logo.png - Included

All set! Your PostArk app is deployment-ready. 🚀
