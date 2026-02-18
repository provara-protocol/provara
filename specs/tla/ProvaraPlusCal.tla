----------------------- MODULE ProvaraPlusCal -----------------------
EXTENDS Naturals, Sequences, FiniteSets

(***************************************************************************
--algorithm Provara {
    variables
        events = << >>,
        chainHeads = [a \in {} |-> ""],
        actors = {},
        signatures = [id \in {} |-> ""],
        merkleRoot = {},
        sealed = FALSE;

    define {
        GenerateEventId == Len(events) + 1
        Hash(e) == e.event_id
        Sign(e, a) == [target |-> e.event_id, signer |-> a]
        ComputeMerkle(evs) == {Hash(evs[i]) : i \in 1..Len(evs)}
        
        MaxEvents == 5
        MaxActors == 3
        EventTypes == {"OBSERVATION", "ATTESTATION"}
    }

    macro AppendEvent(actor, eventType, data) {
        if (~sealed /\ actor \in actors /\ Len(events) < MaxEvents) {
            with (prevHash = if actor \in DOMAIN chainHeads then chainHeads[actor] else "GENESIS") {
                with (newEvent = [
                    event_id |-> GenerateEventId,
                    event_type |-> eventType,
                    actor |-> actor,
                    timestamp |-> Len(events) + 1,
                    prev_event_hash |-> prevHash,
                    data |-> data
                ]) {
                    events := Append(events, newEvent);
                    chainHeads := (if actor \in DOMAIN chainHeads then [chainHeads EXCEPT ![actor] = Hash(newEvent)] else (actor :> Hash(newEvent)) @@ chainHeads);
                    signatures := (newEvent.event_id :> Sign(newEvent, actor)) @@ signatures;
                    merkleRoot := ComputeMerkle(events);
                }
            }
        }
    }

    process (ActorProcess \in 1..MaxActors) {
        Step:
            while (~sealed /\ Len(events) < MaxEvents) {
                either {
                    \* Add actor
                    if (self 
otin actors /\ Cardinality(actors) < MaxActors) {
                        actors := actors \cup {self};
                    }
                } or {
                    \* Append event
                    if (self \in actors) {
                        AppendEvent(self, "OBSERVATION", 0);
                    }
                } or {
                    \* Seal vault
                    Seal:
                        sealed := TRUE;
                }
            }
    }
}
***************************************************************************)
=============================================================================
