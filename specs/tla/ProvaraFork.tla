--------------------------- MODULE ProvaraFork ---------------------------
EXTENDS Provara, Naturals, Sequences

\* Modeling the adversarial scenario: Fork Attack
\* An adversary attempts to create two events with the same prev_event_hash
\* for the same actor, effectively creating a fork in the causal chain.

Adversary == 1 \* For simplicity, actor 1 is the adversary

\* Adversarial action: create a fork
\* This action represents what happens if the causal chain checks are bypassed
\* during event production (e.g., if the adversary manages to sign two events
\* with the same sequence number).
ForkChain(actor, eventType, data) ==
    /\ ~sealed
    /\ actor \in actors
    /\ Len(events) < MaxEvents
    /\ \exists prevHash \in DOMAIN signatures \cup {"GENESIS"}:
        \* The adversary picks a prevHash that is NOT the latest for this actor
        \* (or is the latest, but they've already used it)
        /\ LET newEvent == [
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
          /\ signatures' = (newEvent.event_id :> signature) @@ signatures
          /\ merkleRoot' = ComputeMerkle(events')
          \* We update chainHeads to the new hash, but we've introduced a fork in the history
          /\ chainHeads' = [chainHeads EXCEPT ![actor] = hash]
          /\ UNCHANGED <<actors, sealed>>

\* Fork Detectability:
\* A verifier can detect a fork by scanning the full event log.
ForkDetected ==
    \exists a \in actors:
        \exists e1, e2 \in Range(events):
            /\ e1.actor = a
            /\ e2.actor = a
            /\ e1.event_id /= e2.event_id
            /\ e1.prev_event_hash = e2.prev_event_hash

\* The original NoForks invariant should be violated if ForkChain occurs
NoForksInHistory == 
    \forall a \in actors :
        \forall i, j \in 1..Len(events) :
            (events[i].actor = a /\ events[j].actor = a /\ i /= j)
            => events[i].prev_event_hash /= events[j].prev_event_hash

=============================================================================
