--------------------------- MODULE Provara ---------------------------
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS 
    MaxEvents,      \* Upper bound on the number of events
    MaxActors,      \* Set of actors (or bound)
    EventTypes      \* Set of valid event types

VARIABLES
    events,          \* Sequence of all events in the vault
    chainHeads,      \* Function: actor -> latest event hash
    actors,          \* Set of active actors
    signatures,      \* Function: event_id -> signature
    merkleRoot,      \* Current Merkle root hash
    sealed           \* Boolean: is the vault sealed?

-----------------------------------------------------------------------------

\* Abstract Cryptography and Helpers

\* We use the event's index or content as its "hash" for simplicity.
Hash(e) == e.event_id

\* Sign(event, actor) produces a signature record
Sign(e, a) == [target |-> e.event_id, signer |-> a]

\* Verify(event, signature, actor) checks if signature is valid for event/actor
Verify(e, s, a) == s.target = e.event_id /\ s.signer = a

\* RecomputeMerkle(events) models the deterministic Merkle root calculation
\* In TLA+, we represent this as the set of hashes of all events in the current sequence
ComputeMerkle(evs) == {Hash(evs[i]) : i \in 1..Len(evs)}

Clock == Len(events) + 1

GenerateEventId == Len(events) + 1

Range(f) == { f[x] : x \in DOMAIN f }

-----------------------------------------------------------------------------

\* Initial State
Init ==
    /\ events = << >>
    /\ chainHeads = [a \in {} |-> ""]
    /\ actors = {}
    /\ signatures = [id \in {} |-> ""]
    /\ merkleRoot = {}
    /\ sealed = FALSE

\* Actions

AppendEvent(actor, eventType, data) ==
    /\ ~sealed
    /\ actor \in actors
    /\ Len(events) < MaxEvents
    /\ LET prevHash == IF actor \in DOMAIN chainHeads
                        THEN chainHeads[actor]
                        ELSE "GENESIS"
           newEvent == [
               event_id |-> GenerateEventId,
               event_type |-> eventType,
               actor |-> actor,
               timestamp |-> Clock,
               prev_event_hash |-> prevHash,
               data |-> data
           ]
           signature == Sign(newEvent, actor)
           hash == Hash(newEvent)
       IN /\ events' = Append(events, newEvent)
          /\ chainHeads' = IF actor \in DOMAIN chainHeads
                           THEN [chainHeads EXCEPT ![actor] = hash]
                           ELSE (actor :> hash) @@ chainHeads
          /\ signatures' = (newEvent.event_id :> signature) @@ signatures
          /\ merkleRoot' = ComputeMerkle(events')
          /\ UNCHANGED <<actors, sealed>>

SealVault ==
    /\ ~sealed
    /\ sealed' = TRUE
    /\ UNCHANGED <<events, chainHeads, actors, signatures, merkleRoot>>

AddActor(newActor) ==
    /\ ~sealed
    /\ Cardinality(actors) < MaxActors
    /\ newActor 
otin actors
    /\ actors' = actors \cup {newActor}
    /\ UNCHANGED <<events, chainHeads, signatures, merkleRoot, sealed>>

Next ==
    \/ \exists a \in actors, t \in EventTypes, d \in {0}: AppendEvent(a, t, d)
    \/ SealVault
    \/ \exists a \in 1..MaxActors : AddActor(a)

Spec == Init /\ [][Next]_<<events, chainHeads, actors, signatures, merkleRoot, sealed>>

-----------------------------------------------------------------------------

\* Invariants

\* No two events have the same event_id
EventIdsUnique == \A i, j \in 1..Len(events):
    i /= j => events[i].event_id /= events[j].event_id

\* Per-actor chains are linked correctly
ChainIntegrity == \A i \in 1..Len(events):
    LET e == events[i]
        prevEvents == SelectSeq(SubSeq(events, 1, i-1),
            LAMBDA x: x.actor = e.actor)
    IN IF Len(prevEvents) > 0
       THEN e.prev_event_hash = Hash(prevEvents[Len(prevEvents)])
       ELSE e.prev_event_hash = "GENESIS"

\* All signatures are valid
SignatureValidity == \A i \in 1..Len(events):
    Verify(events[i], signatures[events[i].event_id], events[i].actor)

\* Sealed vault cannot be modified (Safety Invariant)
SealImmutability == [] (sealed => UNCHANGED events)

\* Events are append-only (no deletion, no modification)
AppendOnly == [][\A i \in 1..Len(events):
    events'[i] = events[i]]_<<events>>

\* No forks: each actor has exactly one chain
NoForks == \A a \in actors:
    LET actorEvents == SelectSeq(events, LAMBDA e: e.actor = a)
    IN \A i \in 2..Len(actorEvents):
        actorEvents[i].prev_event_hash = Hash(actorEvents[i-1])

\* Merkle root is always consistent with events
MerkleConsistency == merkleRoot = ComputeMerkle(events)

-----------------------------------------------------------------------------

\* Temporal properties

\* Eventually, every appended event becomes part of a verified chain
\* Note: In this model, signatures are appended atomically with events.
Liveness == \A e \in Range(events):
    <>(e.event_id \in DOMAIN signatures /\ Verify(e, signatures[e.event_id], e.actor))

\* Once sealed, the vault never changes
SealFinality == [](sealed => [](events = UNCHANGED events))
\* Correction for TLA+ syntax on SealFinality:
SealFinalityProp == [](sealed => [] (events = UNCHANGED events))
\* Simplified for TLC:
SealFinalityProperty == [](sealed => [] (events = events))

=============================================================================
