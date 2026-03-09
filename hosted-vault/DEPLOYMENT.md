# Provara Hosted Vault — Deployment Guide

**Version:** 0.1.0  
**Last Updated:** 2026-03-07

---

## Overview

This guide walks you through deploying the Provara Hosted Vault MVP to production. The stack consists of:

- **Vercel** — Serverless API hosting (Edge Functions)
- **Supabase** — PostgreSQL database + Storage bucket
- **Clerk** — JWT authentication
- **Stripe** — Billing and subscriptions

---

## Prerequisites

- [ ] Vercel account (free tier works)
- [ ] Supabase account (free tier works)
- [ ] Clerk account (free tier works)
- [ ] Stripe account (test mode)
- [ ] Node.js 20+ installed
- [ ] Python 3.11+ installed
- [ ] Vercel CLI: `npm i -g vercel`
- [ ] Supabase CLI: `npm i -g supabase`

---

## Step 1: Supabase Setup

### 1.1 Create New Project

1. Go to https://app.supabase.com
2. Click **New Project**
3. Fill in:
   - **Name:** `provara-hosted-vault`
   - **Database Password:** (save to password manager)
   - **Region:** Choose closest to your users
4. Wait ~2 minutes for provisioning

### 1.2 Run Migrations

```bash
cd hosted-vault

# Login to Supabase
supabase login

# Link to your project
supabase link --project-ref <your-project-ref>

# Push migrations
supabase db push
```

Alternatively, run SQL manually:
1. Go to **SQL Editor** in Supabase dashboard
2. Copy contents of `supabase/migrations/001_initial_schema.sql`
3. Paste and run
4. Repeat for `002_vault_keys.sql`

### 1.3 Create Storage Bucket

1. Go to **Storage** in Supabase dashboard
2. Click **New Bucket**
3. Name: `vaults`
4. **Public:** No (private)
5. Click **Create**

### 1.4 Get Credentials

Go to **Settings** → **API**:

- **Project URL:** `https://xxxxx.supabase.co`
- **`service_role` key:** `eyJhbGc...` (keep secret!)
- **`anon` key:** `eyJhbGc...` (for client-side)

Save these for Step 3.

---

## Step 2: Clerk Setup

### 2.1 Create Application

1. Go to https://dashboard.clerk.com
2. Click **Create Application**
3. Name: `Provara Hosted Vault`
4. Choose **Email + Password** sign-in
5. Click **Create**

### 2.2 Configure JWT Template

1. Go to **JWT Templates** in Clerk dashboard
2. Click **Add Template**
3. Name: `provara-vault`
4. Leave default claims
5. Save the **Issuer URL** (e.g., `https://your-instance.clerk.accounts.dev`)

### 2.3 Get Credentials

Go to **API Keys**:

- **Secret Key:** `sk_test_xxx`
- **Publishable Key:** `pk_test_xxx`
- **JWT Issuer:** From step 2.2

Save these for Step 3.

---

## Step 3: Stripe Setup

### 3.1 Create Products

1. Go to https://dashboard.stripe.com/products
2. Click **Add Product**

**Developer Tier:**
- **Name:** `Provara Developer`
- **Description:** `5 vaults, 10K events/month`
- **Pricing:** Recurring, $29/month

**Team Tier:**
- **Name:** `Provara Team`
- **Description:** `Unlimited vaults, 100K events/month`
- **Pricing:** Recurring, $99/month

### 3.2 Get Credentials

Go to **Developers** → **API keys**:

- **Secret key:** `sk_test_xxx`
- **Publishable key:** `pk_test_xxx`

Go to **Developers** → **Webhooks**:

- Click **Add endpoint**
- **Endpoint URL:** `https://your-domain.vercel.app/api/webhooks/stripe`
- **Events:** Select `customer.subscription.*`, `invoice.*`, `payment_intent.*`
- Save the **Signing secret:** `whsec_xxx`

Save all credentials for Step 3.

---

## Step 4: Environment Variables

Create `.env.local` in the `hosted-vault` directory:

```bash
# Clerk
CLERK_SECRET_KEY=sk_test_xxx
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_JWT_ISSUER=https://your-instance.clerk.accounts.dev

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_VAULTS_BUCKET=vaults

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRODUCT_DEVELOPER=prod_xxx
STRIPE_PRICE_DEVELOPER_MONTHLY=price_xxx
STRIPE_PRODUCT_TEAM=prod_xxx
STRIPE_PRICE_TEAM_MONTHLY=price_xxx

# General
NODE_ENV=production
LOG_LEVEL=info
MAX_EVENT_PAYLOAD_BYTES=10240
```

---

## Step 5: Vercel Deployment

### 5.1 Install Vercel CLI

```bash
npm i -g vercel
```

### 5.2 Login

```bash
vercel login
```

### 5.3 Deploy to Preview

```bash
cd hosted-vault
vercel
```

Follow the prompts:
- **Set up and deploy?** Yes
- **Which scope?** Choose your account
- **Link to existing project?** No
- **Project name:** `provara-hosted-vault`
- **Directory:** `./`
- **Want to override settings?** No

### 5.4 Add Environment Variables

Go to your project in Vercel dashboard:

1. **Settings** → **Environment Variables**
2. Add all variables from `.env.local`
3. Set for **Production** and **Preview**

### 5.5 Deploy to Production

```bash
vercel --prod
```

Your API is now live at `https://your-project.vercel.app`

---

## Step 6: Deploy Landing Page

### Option A: Vercel (Same Project)

1. Move `site/index.html` to root or configure rewrites
2. Redeploy

### Option B: Cloudflare Pages (Recommended for provara.app)

1. Go to https://pages.cloudflare.com
2. **Create a project** → **Direct Upload**
3. Upload `site/index.html`
4. **Project name:** `provara-app`
5. **Production branch:** `main`
6. Click **Deploy**

Connect your domain `provara.app` in Cloudflare DNS settings.

---

## Step 7: Testing

### 7.1 Health Check

```bash
curl https://your-project.vercel.app/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-07T...",
  "checks": {
    "supabase": {"status": "healthy"},
    "clerk": {"status": "healthy"},
    "storage": {"status": "healthy"}
  }
}
```

### 7.2 Create a Vault

First, get a Clerk JWT token (use their test tool or sign in via your app).

```bash
export CLERK_TOKEN="your_jwt_token"

curl -X POST https://your-project.vercel.app/api/v1/vaults \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-vault", "description": "My first vault"}'
```

### 7.3 Append an Event

```bash
export VAULT_ID="vlt_xxx"

curl -X POST https://your-project.vercel.app/api/v1/vaults/$VAULT_ID/events \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "note",
    "data": {"message": "Hello, Provara!"}
  }'
```

### 7.4 Query Events

```bash
curl -X GET https://your-project.vercel.app/api/v1/vaults/$VAULT_ID/events \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

### 7.5 Verify Vault

```bash
curl -X GET https://your-project.vercel.app/api/v1/vaults/$VAULT_ID/events?action=verify \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

---

## Step 8: Monitoring Setup

### 8.1 Sentry (Optional but Recommended)

1. Go to https://sentry.io
2. Create new project (Python + Node.js)
3. Get DSN
4. Add to Vercel env vars: `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`

### 8.2 Vercel Analytics

1. Go to **Analytics** in Vercel dashboard
2. Enable for your project
3. View real-time metrics

### 8.3 Supabase Logs

1. Go to **Logs** in Supabase dashboard
2. Filter by table or function
3. Set up alerts for errors

---

## Step 9: Production Checklist

Before going live:

- [ ] Switch Stripe to **Live Mode**
- [ ] Create live products and prices
- [ ] Update all Stripe credentials to live keys
- [ ] Update Clerk to **Production** instance
- [ ] Update Supabase to **Production** project (if using separate dev/prod)
- [ ] Set up custom domain in Vercel
- [ ] Enable HTTPS (automatic with Vercel)
- [ ] Configure CORS for your domain
- [ ] Set up error alerting (Sentry, Vercel)
- [ ] Test full user flow end-to-end
- [ ] Create backup strategy for Supabase data
- [ ] Document runbook for common issues

---

## Troubleshooting

### "Vault not found"

Check:
1. Vault ID is correct (UUID format)
2. JWT token belongs to vault owner
3. Vault status is `active` (not `deleted`)

### "Signature verification failed"

Check:
1. Supabase `vault_keys` table has entry for vault
2. Private key PEM is valid
3. Key fingerprint matches `vaults.key_id`

### Rate limit errors

Check:
1. User's tier in `stripe_customers` table
2. Current usage in `usage_tracking` table
3. Tier limits in `get_tier_limits()` function

### Database migration fails

```bash
# Check migration status
supabase migration list

# Reset and re-run (dev only!)
supabase db reset
supabase db push
```

---

## Cost Estimate (Monthly)

| Service | Free Tier | Paid (100 users) |
|---------|-----------|------------------|
| Vercel | $0 | $20 (Pro) |
| Supabase | $0 | $25 (Pro) |
| Clerk | $0 | $25 (Plus) |
| Stripe | $0 | 2.9% + $0.30/transaction |
| **Total** | **$0** | **~$70 + transaction fees** |

---

## Next Steps

1. **Webhook Integration:** Implement Stripe webhook handler for subscription events
2. **Email Notifications:** Add Resend/SendGrid for welcome emails, usage alerts
3. **Dashboard UI:** Build React dashboard for vault management
4. **Analytics:** Add PostHog or Mixpanel for user behavior tracking
5. **Documentation:** Publish API docs at `docs.provara.app`

---

## Support

- **GitHub Issues:** https://github.com/provara-protocol/provara/issues
- **Discord:** (coming soon)
- **Email:** support@provara.dev

---

*End of Deployment Guide*
