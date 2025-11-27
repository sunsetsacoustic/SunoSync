# SunoSync 🎵 (v2.4.0)

Download your **entire** Suno AI music library in seconds — with lyrics, album art, prompts, tags, and perfect metadata!

## ⚠️ Important Legal Notice
- This tool is **unofficial** and **not affiliated** with Suno AI  
- Use **only for personal backup** of songs you created  
- Downloading and redistributing Suno songs may violate their [Terms of Service](https://suno.com/terms)  
- Pro/Premier users: sharing downloaded songs can risk your account  
- **Use at your own risk** — the developer is not responsible for bans or issues

## Features
- ✨ Smart resume — never downloads the same song twice  
- 🎨 Full metadata & embedded album art (title, artist, genre, year, lyrics, prompt)  
- 📁 Optional monthly folders (2024-11, 2025-01, etc.)  
- 🔄 Automatic retries on network errors  
- ⚡ Super-fast concurrent downloads (10+ songs at once)  
- 💾 Saves your token & settings forever  
- ⏱️ Shows real-time progress, speed, and ETA  

## Installation (Windows only)
1. Download → [`SunoApiDownloader.exe`](https://github.com/yourname/suno-downloader/releases/latest)  
2. Double-click to run — **no installation needed!**  
3. Done 🎉

## How to Use

### Step 1: Get Your Auth Token
**Method A (Recommended - works 99% of the time)**
1. Click **"Get Token (Login)"** in the app  
2. Log in to https://suno.com in your browser  
3. Press **F12** → go to **Console** tab  
4. Paste this and press Enter:
   ```js
   window.Clerk?.session?.getToken().then(t => prompt('Your token (copy this):', t))
   ```
5. Copy the token and paste it back into the app

**Method B (if Method A fails)**
1. Open https://suno.com and log in  
2. Press F12 → Network tab  
3. Click any song or refresh the page  
4. Find a request to `api.suno.com` or `gql.suno.com`  
5. Copy the value after `authorization: Bearer ` → that’s your token

🔑 **Never share your token** — it’s like giving someone full access to your Suno account!

### Step 2: Configure (recommended settings)
- ✅ **Embed Metadata & Art** → ON (highly recommended)  
- ⬜ **Organize by Month** → ON (keeps things tidy if you have 1000+ songs)  
- **Start from Page** → 1 (or higher to resume)  
- **Max Pages** → 0 = download everything  

### Step 3: Download!
1. Click **START DOWNLOAD**  
2. Grab coffee ☕ — it’s fast  
3. Click **Open Folder** when finished  

## Example Workflows

| Goal                        | Start from Page | Max Pages | Result                     |
|-----------------------------|-----------------|-----------|----------------------------|
| Download everything         | 1               | 0         | Your full library          |
| First 500 songs             | 1               | 10        | ~500 oldest songs          |
| Next 1000 songs             | 11              | 20        | Pages 11–30                |
| Resume after crash          | 23              | 0         | Continues from page 23     |

## Tips & Tricks
- Already downloaded songs are **automatically skipped**  
- Use **STOP** anytime — just restart later and it resumes perfectly  
- Large libraries (>5000 songs)? Download in chunks of 20–30 pages  
- Want clean filenames? Keep “Embed Metadata” ON  

## Requirements
- Windows 10 or 11 (64-bit)  
- Internet connection  
- Active Suno account (free or paid)

## Known Issues
- Very rarely, Suno changes their API → token stops working (just get a new one)  
- Some extremely old songs (pre-June 2024) may have missing metadata

## Support the Developer
Loved this tool? Buy me a coffee! ☕  
→ https://buymeacoffee.com/audioalchemy

## Made with ❤️ for the Suno AI community

(Last updated: November 26, 2025)
