--------------------------- MODULE provara_chain ---------------------------
EXTENDS Naturals, Sequences, Sets

(***************************************************************************
 * PROVARA PROTOCOL v1.0 — TLA+ Specification
 *
 * This spec models the core causal chain invariants, signature 
 * non-repudiation, and key rotation protocol defined in 
 * PROTOCOL_PROFILE.txt.
 ***************************************************************************)

CONSTANTS
    Actors,      \* Set of all potential actors
    Keys         \* Set of all potential cryptographic keys

VARIABLES
    \* The vault state: a map from Actor to a sequence of events
    vault,
    \* The set of active/authorized keys for each actor
    activeKeys,
    \* The set of revoked keys for each actor
    revokedKeys,
    \* The set of all events ever produced (global set for id uniqueness)
    allEvents

-----------------------------------------------------------------------------

\* Helpers
Nil == "NIL"

\* An event is a record: 
\* [id: ID, actor: Actor, prev: ID|Nil, key: Key, sig: Valid]
\* In this model, we represent the hash content by the fields themselves.
\* sig is modeled as being valid if signed by an authorized key at time of creation.

ValidEvents == [
    id: NAT, 
    actor: Actors, 
    prev: NAT \cup {Nil}, 
    key: Keys,
    type: {"GENESIS", "OBSERVATION", "KEY_REVOCATION", "KEY_PROMOTION"}
]

\* Type Invariant
TypeOK ==
    /\ vault \in [Actors -> Seq(ValidEvents)]
    /\ activeKeys \in [Actors -> SUBSET Keys]
    /\ revokedKeys \in [Actors -> SUBSET Keys]
    /\ allEvents \in SUBSET ValidEvents

\* Invariants to check

\* 1. Hash Chain Integrity: Every event's prev points to the id of the previous event.
ChainIntegrity ==
    \forall a \in Actors :
        \forall i \in 2..Len(vault[a]) :
            vault[a][i].prev = vault[a][i-1].id

\* 2. Signature Non-Repudiation: Every event was signed by a key that was active at that time.
\* (Implicit in the Append action, but we check consistency)
SignatureValid ==
    \forall a \in Actors :
        \forall e \in Range(vault[a]) :
            e.key \notin revokedKeys[a]

\* 3. Fork Detection: All events by an actor in the vault have unique IDs and a linear history.
\* (Implicit in Seq structure, but allEvents tracks globally)
NoGlobalCollisions ==
    \forall e1, e2 \in allEvents :
        e1.id = e2.id => e1 = e2

-----------------------------------------------------------------------------

\* Initial State
Init ==
    /\ vault = [a \in Actors -> << >>]
    /\ activeKeys = [a \in Actors -> {CHOOSE k \in Keys : TRUE}] \* Bootstrap with one key
    /\ revokedKeys = [a \in Actors -> {}]
    /\ allEvents = {}

\* Actions

\* Append a data event (OBSERVATION)
Append(a, k) ==
    /\ k \in activeKeys[a]
    /\ \LET newId == IF allEvents = {} THEN 1 ELSE (CHOOSE n \in NAT : \forall e \in allEvents : n > e.id)
            prevId == IF vault[a] = << >> THEN Nil ELSE vault[a][Len(vault[a])].id
            type   == IF vault[a] = << >> THEN "GENESIS" ELSE "OBSERVATION"
            event  == [id |-> newId, actor |-> a, prev |-> prevId, key |-> k, type |-> type]
       \IN
            /\ vault' = [vault EXCEPT ![a] = Append(vault[a], event)]
            /\ allEvents' = allEvents \cup {event}
            /\ UNCHANGED <<activeKeys, revokedKeys>>

\* Key Rotation Step 1: Revocation
\* Must be signed by a surviving authority (another active key)
RevokeKey(a, authorityKey, targetKey) ==
    /\ authorityKey \in activeKeys[a]
    /\ targetKey \in activeKeys[a]
    /\ authorityKey /= targetKey
    /\ vault[a] /= << >>
    /\ \LET newId == (CHOOSE n \in NAT : \forall e \in allEvents : n > e.id)
            prevId == vault[a][Len(vault[a])].id
            event  == [id |-> newId, actor |-> a, prev |-> prevId, key |-> authorityKey, type |-> "KEY_REVOCATION"]
       \IN
            /\ vault' = [vault EXCEPT ![a] = Append(vault[a], event)]
            /\ allEvents' = allEvents \cup {event}
            /\ activeKeys' = [activeKeys EXCEPT ![a] = activeKeys[a] \ {targetKey}]
            /\ revokedKeys' = [revokedKeys EXCEPT ![a] = revokedKeys[a] \cup {targetKey}]

\* Key Rotation Step 2: Promotion
\* A surviving authority promotes a new key
PromoteKey(a, authorityKey, newKey) ==
    /\ authorityKey \in activeKeys[a]
    /\ newKey \notin activeKeys[a]
    /\ newKey \notin revokedKeys[a]
    /\ vault[a] /= << >>
    /\ \LET newId == (CHOOSE n \in NAT : \forall e \in allEvents : n > e.id)
            prevId == vault[a][Len(vault[a])].id
            event  == [id |-> newId, actor |-> a, prev |-> prevId, key |-> authorityKey, type |-> "KEY_PROMOTION"]
       \IN
            /\ vault' = [vault EXCEPT ![a] = Append(vault[a], event)]
            /\ allEvents' = allEvents \cup {event}
            /\ activeKeys' = [activeKeys EXCEPT ![a] = activeKeys[a] \cup {newKey}]
            /\ UNCHANGED revokedKeys

\* Next State
Next ==
    \exists a \in Actors :
        \/ \exists k \in activeKeys[a] : Append(a, k)
        \/ \exists k1, k2 \in activeKeys[a] : RevokeKey(a, k1, k2)
        \/ \exists k1 \in activeKeys[a], k2 \in Keys : PromoteKey(a, k1, k2)

Spec == Init /\ [][Next]_<<vault, activeKeys, revokedKeys, allEvents>>

-----------------------------------------------------------------------------

\* Theorems / Properties to verify
\* Liveness: Eventually every actor can append an event (unless all keys revoked, which shouldn't happen here)
\* For this simple model, we mostly care about the safety invariants.

=============================================================================
