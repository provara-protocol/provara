"""
perception_v0.py — Backpack v1.0 Perception Tiering System

Implements the T0-T3 sensor data hierarchy:
  T0: Raw sensor data (e.g. images, audio) -> 30-day retention
  T1: Object detections & classifications  -> 1-year retention
  T2: Scene understanding & relationships  -> 5-year retention
  T3: High-level summaries & insights      -> Permanent retention
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

class PerceptionTier(Enum):
    T0_RAW = "T0"
    T1_OBJECT = "T1"
    T2_SCENE = "T2"
    T3_SUMMARY = "T3"

def create_perception_payload(
    tier: PerceptionTier,
    subject: str,
    value: Any,
    confidence: float = 1.0,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cas_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a structured payload for an OBSERVATION or ASSERTION event.
    """
    payload = {
        "tier": tier.value,
        "subject": subject,
        "predicate": "perception",
        "value": value,
        "confidence": confidence,
    }
    
    if timestamp:
        payload["timestamp"] = timestamp
    
    if metadata:
        payload["metadata"] = metadata
        
    if cas_ref:
        payload["cas_ref"] = cas_ref
        
    return payload

def emit_perception_event(
    actor: str,
    tier: PerceptionTier,
    subject: str,
    value: Any,
    confidence: float = 1.0,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cas_ref: Optional[str] = None,
    prev_event_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produce a complete, unsigned Provara perception event.
    """
    # T0 is usually an OBSERVATION, T3 is usually an ASSERTION.
    # T1/T2 can be either, but let's default to OBSERVATION for T0-T1, 
    # and ASSERTION for T2-T3.
    event_type = "OBSERVATION"
    if tier in [PerceptionTier.T2_SCENE, PerceptionTier.T3_SUMMARY]:
        event_type = "ASSERTION"
        
    payload = create_perception_payload(
        tier=tier,
        subject=subject,
        value=value,
        confidence=confidence,
        timestamp=timestamp,
        metadata=metadata,
        cas_ref=cas_ref
    )
    
    return {
        "type": event_type,
        "actor": actor,
        "prev_event_hash": prev_event_hash,
        "payload": payload,
    }
