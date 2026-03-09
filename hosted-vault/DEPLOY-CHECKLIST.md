# Provara Hosted Vault — 45-Minute Deploy Checklist

**Target:** Production-ready in 45 minutes  
**Date:** 2026-03-07  
**Owner:** Chase

---

## ⏱️ Time Box

| Step | Time | Cumulative |
|------|------|------------|
| 1. Supabase setup | 10 min | 10 min |
| 2. Clerk setup | 8 min | 18 min |
| 3. Stripe setup | 10 min | 28 min |
| 4. Vercel deploy | 10 min | 38 min |
| 5. Test + verify | 7 min | 45 min |

---

## □ Step 1: Supabase (10 min)

### 1.1 Create Project (3 min)
- [ ] Go to https://app.supabase.com
- [ ] Click **New Project**
- [ ] Name: `provara-hosted-vault`
- [ ] DB password: (generate + save to Bitwarden)
- [ ] Region: `us-east-1` (closest to most users)
- [ ] Wait for provisioning (~2 min)

### 1.2 Run Migrations (5 min)
- [ ] Open **SQL Editor** in Supabase dashboard
- [ ] Copy `supabase/migrations/001_initial_schema.sql`
- [ ] Paste → Run
- [ ] Copy `supabase/migrations/002_vault_keys.sql`
- [ ] Paste → Run
- [ ] Verify: 6 tables created (vaults, events, api_keys, usage_tracking, stripe_customers, vault_keys)

### 1.3 Create Storage Bucket (2 min)
- [ ] Go to **Storage**
- [ ] **New Bucket** → Name: `vaults`
- [ ] **Public:** No
- [ ] **Create**

### 1.4 Copy Credentials (1 min)
- [ ] Go to **Settings** → **API**
- [ ] Copy **Project URL**: `https://xxxxx.supabase.co`
- [ ] Copy **service_role key**: `eyJhbGc...`
- [ ] Save to `.env.local`

**Supabase Done:** ✅

---

## □ Step 2: Clerk (8 min)

### 2.1 Create Application (4 min)
- [ ] Go to https://dashboard.clerk.com
- [ ] **Create Application**
- [ ] Name: `Provara Hosted Vault`
- [ ] Sign-in: **Email + Password** (enable)
- [ ] **Create**

### 2.2 Configure JWT (2 min)
- [ ] Go to **JWT Templates**
- [ ] **Add Template** → Name: `provara`
- [ ] Leave defaults → **Save**
- [ ] Copy **Issuer URL**: `https://xxx.clerk.accounts.dev`

### 2.3 Copy Credentials (2 min)
- [ ] Go to **API Keys**
- [ ] Copy **Secret Key**: `sk_test_xxx`
- [ ] Copy **Publishable Key**: `pk_test_xxx`
- [ ] Save to `.env.local`

**Clerk Done:** ✅

---

## □ Step 3: Stripe (10 min)

### 3.1 Enable Test Mode (1 min)
- [ ] Toggle **Test Mode** ON (top right)

### 3.2 Create Products (6 min)

**Developer Tier:**
- [ ] **Products** → **Add Product**
- [ ] Name: `Provara Developer`
- [ ] Pricing: **Recurring** → $29/month
- [ ] Description: `5 vaults, 10K events/month`
- [ ] **Save**
- [ ] Copy **Product ID**: `prod_xxx`
- [ ] Copy **Price ID**: `price_xxx`

**Team Tier:**
- [ ] **Add Product**
- [ ] Name: `Provara Team`
- [ ] Pricing: **Recurring** → $99/month
- [ ] Description: `Unlimited vaults, 100K events/month`
- [ ] **Save**
- [ ] Copy **Product ID**: `prod_xxx`
- [ ] Copy **Price ID**: `price_xxx`

### 3.3 Configure Webhook (2 min)
- [ ] **Developers** → **Webhooks**
- [ ] **Add Endpoint**
- [ ] URL: `https://CHANGEME.vercel.app/api/webhooks/stripe` (update after Vercel deploy)
- [ ] Events: `customer.subscription.*`, `invoice.payment.*`
- [ ] **Save**
- [ ] Copy **Signing Secret**: `whsec_xxx`

### 3.4 Copy Credentials (1 min)
- [ ] **Developers** → **API Keys**
- [ ] Copy **Secret Key**: `sk_test_xxx`
- [ ] Copy **Publishable Key**: `pk_test_xxx`
- [ ] Save to `.env.local`

**Stripe Done:** ✅

---

## □ Step 4: Vercel Deploy (10 min)

### 4.1 Install CLI (if needed) (2 min)
```bash
npm i -g vercel
vercel login
```

### 4.2 Deploy (5 min)
```bash
cd hosted-vault
vercel
```

**Prompts:**
- Set up and deploy? **Yes**
- Which scope? **(choose your account)**
- Link to existing? **No**
- Project name: `provara-hosted-vault`
- Directory: `./`
- Override settings? **No**

### 4.3 Add Environment Variables (3 min)

Go to Vercel Dashboard → Your Project → **Settings** → **Environment Variables**

Add these (Production + Preview):
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
CLERK_SECRET_KEY=sk_test_xxx
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_JWT_ISSUER=https://xxx.clerk.accounts.dev
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRODUCT_DEVELOPER=prod_xxx
STRIPE_PRICE_DEVELOPER_MONTHLY=price_xxx
STRIPE_PRODUCT_TEAM=prod_xxx
STRIPE_PRICE_TEAM_MONTHLY=price_xxx
NODE_ENV=production
```

### 4.4 Redeploy with Env Vars
```bash
vercel --prod
```

**Vercel Done:** ✅

---

## □ Step 5: Test + Verify (7 min)

### 5.1 Health Check (2 min)
```bash
curl https://provara-hosted-vault.vercel.app/api/health
```

**Expected:**
```json
{
  "status": "healthy",
  "checks": {
    "supabase": {"status": "healthy"},
    "clerk": {"status": "healthy"},
    "storage": {"status": "healthy"}
  }
}
```

### 5.2 Update Stripe Webhook URL (2 min)
- [ ] Go back to Stripe Webhook settings
- [ ] Update URL to your actual Vercel URL
- [ ] **Save**

### 5.3 Create Test Vault (3 min)

Get a Clerk JWT (use their test token or sign in):

```bash
export CLERK_TOKEN="your_test_token"

curl -X POST https://provara-hosted-vault.vercel.app/api/v1/vaults \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-vault"}'
```

**Expected:** `201 Created` with vault_id

---

## ✅ Done — Production Live

**Next Actions:**
1. Connect custom domain in Vercel (`api.provara.app`)
2. Deploy landing page to `provara.app`
3. Switch Stripe to **Live Mode** (when ready for real payments)
4. Share on HN/Twitter

---

## 🚨 Troubleshooting

| Error | Fix |
|-------|-----|
| "Supabase credentials not configured" | Check env vars in Vercel |
| "Vault not found" | Verify JWT token belongs to vault owner |
| "Signature verification failed" | Check vault_keys table has entry |
| 500 error on deploy | Check Vercel function logs |

---

*Checklist version: 0.1.0 | Last updated: 2026-03-07*
