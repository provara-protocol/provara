# Cloudflare Pages Setup — Provara Protocol

**Copy/paste this into Cloudflare Pages setup, or use as your checklist.**

---

## Account Setup

1. **Log into Cloudflare** → https://dash.cloudflare.com/
2. **Go to Pages** → https://dash.cloudflare.com/?to=/:account/pages
3. **Click "Create a project"**

---

## Project 1: provara.dev

### Step 1: Connect GitHub

```
Repository: provara-protocol/provara
Branch: main
```

### Step 2: Build Settings

```
Framework preset: None (static site)
Build command: [leave blank]
Build output directory: sites/dev
Root directory: [leave blank]
Environment variables: [none needed]
```

### Step 3: Domain

```
Custom domain: provara.dev
Production branch: main
```

### Step 4: Deploy

```
Click "Save and Deploy"
Wait ~30 seconds for first deploy
```

---

## Project 2: provara.app

### Step 1: Connect GitHub

```
Repository: provara-protocol/provara
Branch: main
```

### Step 2: Build Settings

```
Framework preset: None (static site)
Build command: [leave blank]
Build output directory: sites/app
Root directory: [leave blank]
Environment variables: [none needed]
```

### Step 3: Domain

```
Custom domain: provara.app
Production branch: main
```

### Step 4: Deploy

```
Click "Save and Deploy"
Wait ~30 seconds for first deploy
```

---

## Project 3: huntinformationsystems.com

### Step 1: Connect GitHub

```
Repository: provara-protocol/provara
Branch: main
```

### Step 2: Build Settings

```
Framework preset: None (static site)
Build command: [leave blank]
Build output directory: sites/his
Root directory: [leave blank]
Environment variables: [none needed]
```

### Step 3: Domain

```
Custom domain: huntinformationsystems.com
Production branch: main
```

### Step 4: Deploy

```
Click "Save and Deploy"
Wait ~30 seconds for first deploy
```

---

## DNS Configuration (At GoDaddy)

**After creating each Cloudflare Pages project, update DNS at GoDaddy:**

### For provara.dev

```
Log into GoDaddy → Domain Settings → DNS

Add CNAME Record:
- Type: CNAME
- Name: @
- Value: provara-dev.pages.dev
- TTL: Default

Add CNAME Record (optional, for www):
- Type: CNAME
- Name: www
- Value: provara-dev.pages.dev
- TTL: Default
```

### For provara.app

```
Log into GoDaddy → Domain Settings → DNS

Add CNAME Record:
- Type: CNAME
- Name: @
- Value: provara-app.pages.dev
- TTL: Default

Add CNAME Record (optional, for www):
- Type: CNAME
- Name: www
- Value: provara-app.pages.dev
- TTL: Default
```

### For huntinformationsystems.com

```
Log into GoDaddy → Domain Settings → DNS

Add CNAME Record:
- Type: CNAME
- Name: @
- Value: hunt-his.pages.dev
- TTL: Default

Add CNAME Record (optional, for www):
- Type: CNAME
- Name: www
- Value: hunt-his.pages.dev
- TTL: Default
```

---

## SSL/HTTPS Settings (Cloudflare)

**For each project:**

1. **Go to Pages → [Project Name] → Custom domains**
2. **Click "Manage custom domain"**
3. **Enable:**
   - ✅ HTTPS (automatic)
   - ✅ Force HTTPS (redirect HTTP → HTTPS)
   - ✅ HTTP Strict Transport Security (HSTS)

**Cloudflare provides free SSL certificates automatically.**

---

## Verification Checklist

After setup, verify each domain:

```
[ ] provara.dev loads (https://provara.dev)
[ ] provara.app loads (https://provara.app)
[ ] huntinformationsystems.com loads (https://huntinformationsystems.com)
[ ] All redirect HTTP → HTTPS
[ ] No SSL warnings in browser
[ ] Cloudflare proxy is active (orange cloud in DNS)
```

---

## Troubleshooting

### "Domain already connected to another project"

```
Solution: Go to the other project → Settings → Custom domains → Remove domain
Then add to correct project.
```

### "DNS propagation taking too long"

```
Wait 5-30 minutes. Use https://dnschecker.org/ to verify propagation.
```

### "SSL certificate not issued yet"

```
Wait 15-60 minutes. Cloudflare auto-issues certificates.
Force refresh: Ctrl+Shift+R (Chrome) or Cmd+Shift+R (Firefox).
```

### "404 Not Found"

```
Check build output directory matches your folder structure:
- sites/dev for provara.dev
- sites/app for provara.app
- sites/his for huntinformationsystems.com

If folders don't exist yet, create placeholder index.html:
  <!DOCTYPE html>
  <html><head><title>Coming Soon</title></head>
  <body><h1>Provara — Coming Soon</h1></body></html>
```

---

## Post-Deployment: Enable Cloudflare Features

**For each project, enable:**

1. **Automatic Platform Optimization (APO)**
   - Pages → [Project] → Speed → APO → Enable
   - Free for Pages

2. **Early Hints**
   - Pages → [Project] → Speed → Early Hints → Enable
   - Improves load time

3. **Web Analytics** (optional)
   - Pages → [Project] → Analytics → Enable
   - Privacy-friendly (no cookies)

4. **Bot Fight Mode** (recommended)
   - Security → Bots → Bot Fight Mode → Enable
   - Free tier includes basic bot protection

---

## Ongoing Maintenance

### Automatic Deploys

```
Every push to main branch → automatic deploy
No action needed. Cloudflare watches GitHub.
```

### Rollback (if needed)

```
Pages → [Project] → Deployments → Click previous deploy → "Rollback"
```

### View Logs

```
Pages → [Project] → Deployments → Click deploy → "View logs"
```

### Custom Build Settings (if needed later)

```
Pages → [Project] → Settings → Build & deployments → Build configuration
```

---

## Cost Estimate

| Feature | Cost |
|---------|------|
| **Cloudflare Pages** | Free (unlimited sites, 100GB bandwidth/mo) |
| **SSL certificates** | Free (included) |
| **DNS management** | Free (included) |
| **Bot protection** | Free (basic tier) |
| **Web analytics** | Free (included) |
| **Total** | **$0/month** |

---

## Support Resources

- **Cloudflare Pages Docs:** https://developers.cloudflare.com/pages/
- **Custom Domains:** https://developers.cloudflare.com/pages/platform/custom-domains/
- **Community Forum:** https://community.cloudflare.com/
- **Status Page:** https://www.cloudflarestatus.com/

---

**Setup time:** ~30 minutes for all 3 domains
**First deploy:** ~30 seconds per project
**DNS propagation:** 5-30 minutes

**You're done when all 3 domains load with HTTPS.** 🚀
