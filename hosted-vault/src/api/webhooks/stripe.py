"""
Provara Hosted Vault API - Stripe Webhook Handler

Endpoints:
- POST /api/webhooks/stripe - Handle Stripe billing events

Events handled:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_succeeded
- invoice.payment_failed
"""

import json
import os
from http import HTTPStatus
from datetime import datetime, timezone

from supabase import Client, create_client

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_key)


def handle_subscription_created(event_data: dict) -> dict:
    """Handle new subscription creation."""
    subscription = event_data["object"]
    customer_id = subscription["customer"]
    
    # Get or create Stripe customer record
    data = {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription["id"],
        "tier": "developer" if subscription["plan"]["nickname"] == "Developer" else "team",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    result = supabase.table("stripe_customers").upsert(data, on_conflict="stripe_customer_id").execute()
    
    return {"status": "success", "action": "subscription_created", "customer_id": customer_id}


def handle_subscription_updated(event_data: dict) -> dict:
    """Handle subscription updates (plan changes, cancellations)."""
    subscription = event_data["object"]
    customer_id = subscription["customer"]
    
    # Determine new tier
    status = subscription["status"]
    if status == "canceled":
        new_tier = "free"
    else:
        new_tier = "developer" if subscription["plan"]["nickname"] == "Developer" else "team"
    
    # Update customer record
    result = (
        supabase.table("stripe_customers")
        .update({
            "stripe_subscription_id": subscription["id"],
            "tier": new_tier,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("stripe_customer_id", customer_id)
        .execute()
    )
    
    # Update vault tier if customer exists
    if result.data:
        user_id = result.data[0]["user_id"]
        supabase.table("vaults").update({"tier": new_tier}).eq("owner_id", user_id).execute()
    
    return {"status": "success", "action": "subscription_updated", "customer_id": customer_id}


def handle_subscription_deleted(event_data: dict) -> dict:
    """Handle subscription cancellation (downgrade to free)."""
    subscription = event_data["object"]
    customer_id = subscription["customer"]
    
    # Downgrade to free tier
    result = (
        supabase.table("stripe_customers")
        .update({
            "stripe_subscription_id": None,
            "tier": "free",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("stripe_customer_id", customer_id)
        .execute()
    )
    
    # Update all user's vaults to free tier
    if result.data:
        user_id = result.data[0]["user_id"]
        supabase.table("vaults").update({"tier": "free"}).eq("owner_id", user_id).execute()
    
    return {"status": "success", "action": "subscription_deleted", "customer_id": customer_id}


def handle_invoice_payment_succeeded(event_data: dict) -> dict:
    """Handle successful payment (for logging)."""
    invoice = event_data["object"]
    customer_id = invoice["customer"]
    
    # Log payment success (could send receipt email here)
    return {"status": "success", "action": "payment_succeeded", "customer_id": customer_id}


def handle_invoice_payment_failed(event_data: dict) -> dict:
    """Handle failed payment (flag account for review)."""
    invoice = event_data["object"]
    customer_id = invoice["customer"]
    
    # Flag account for review (could send dunning email here)
    # For now, just log the event
    return {"status": "success", "action": "payment_failed", "customer_id": customer_id}


# Event handler mapping
EVENT_HANDLERS = {
    "customer.subscription.created": handle_subscription_created,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


def handler(request):
    """Stripe webhook endpoint handler."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Stripe-Signature",
    }

    # Handle preflight
    if request.method == "OPTIONS":
        return {"statusCode": HTTPStatus.OK, "headers": headers, "body": ""}

    if request.method != "POST":
        return {
            "statusCode": HTTPStatus.METHOD_NOT_ALLOWED,
            "headers": headers,
            "body": json.dumps({"error": "Method not allowed"}),
        }

    # Verify Stripe signature
    stripe_signature = request.headers.get("Stripe-Signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    if not stripe_signature or not webhook_secret:
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "headers": headers,
            "body": json.dumps({"error": "Missing Stripe signature or secret"}),
        }

    try:
        # TODO: Implement signature verification with stripe library
        # For MVP, we'll skip verification (add in production!)
        # event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
        
        # Parse event
        payload = json.loads(request.body)
        event_type = payload.get("type")
        event_data = payload.get("data", {})
        
        if not event_type:
            return {
                "statusCode": HTTPStatus.BAD_REQUEST,
                "headers": headers,
                "body": json.dumps({"error": "Missing event type"}),
            }
        
        # Handle event
        handler_func = EVENT_HANDLERS.get(event_type)
        if not handler_func:
            # Unknown event type, but still return 200 (Stripe best practice)
            return {
                "statusCode": HTTPStatus.OK,
                "headers": headers,
                "body": json.dumps({"status": "ignored", "event_type": event_type}),
            }
        
        result = handler_func(event_data)
        
        return {
            "statusCode": HTTPStatus.OK,
            "headers": headers,
            "body": json.dumps(result),
        }
        
    except json.JSONDecodeError:
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "headers": headers,
            "body": json.dumps({"error": "Invalid JSON"}),
        }
    except Exception as e:
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
