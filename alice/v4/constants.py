"""Every constant of V4's dynamics, in one place (spec §4.4).

The values are the spec's initial guesses (§6). They may be changed only in the pilots P0 and P1, on development
scenarios, with each change and its reason recorded in specs/v4/tuning-log.md. Before the battery they are frozen:
the hash of this file goes into every run's metadata, and a change after that is a new version of V4.

Units: time in sim minutes unless a name says otherwise; rates are per minute; activations and most drives 0..1.
"""

# ---------- integration ----------
DT_MIN = 1.0                 # integration step (overridden by ALICE_V4_DT_MIN)
LOG_EVERY_STEPS = 5          # per-step logs (field_top, drives, gate): every 5th step. Logging only, not dynamics:
                             # every step would make each probe fork of a 40-day run ~40 MB
FIELD_TOP_N = 20             # nodes per field_top row

CONVERSATION_IDLE_MIN = 30.0  # "in conversation" (gate closed) until 30 min after the last message, not until V1
                             # closes the session 3 h later (tuning log, entry 0)

# ---------- nodes and edges (§6.1) ----------
TAU_MIN = 30.0               # decay time constant of activation
TAU_AROUSAL_GAIN = 1.0       # τ × (1 + arousal_tag) for emotionally charged nodes (3 in the spec: entry 8)
EDGE_TOP_K = 16              # similarity edges at creation
EDGE_MIN_COS = 0.35          # weight = (cos − 0.35) / (1 − 0.35)
LINK_WEIGHT = 0.5            # V1's led_to / related links
TRACE_WEIGHT = 0.6           # a trace to its session's episode and to the user
THOUGHT_WEIGHT = 0.5         # a thought to the coalition it came from
COMMITMENT_USER_WEIGHT = 0.5  # an intention made in conversation to the user node
OWN_LINK_WEIGHT = 0.2        # the agent's own nodes to the self node
OWN_INPUT = 0.3              # own nodes get input × 0.3 (D6 of V3)

# ---------- field dynamics (§6.2) ----------
SPREAD_GAIN = 0.006          # g_spread at arousal 0.5, awake
SPREAD_AROUSAL = 0.6         # g × (0.7 + 0.6·arousal)
SPREAD_SLOPE, SPREAD_MID = 8.0, 0.4   # f(a) = sigmoid(8·(a − 0.4))
SPREAD_NORMALIZE = True      # spreading ÷ max(1, Σ_j w_ij) (tuning log, entry 0)
RESTING_BETA = 0.006         # β · σ(B): frequently used nodes are easier to light
TUG_MAX = 0.01               # unfinished business: u · TUG_MAX · (1 − 0.5^(h / TUG_REST_H))
TUG_REST_H = 24.0
NOISE_SIGMA = 0.005          # σ_noise awake (Ornstein–Uhlenbeck, unit stationary variance)
NOISE_TAU = 10.0             # correlation time of the noise
INHIBITION_IOTA = 0.6        # ι = 0.6 · focus
INHIBITION_RATE = 0.05       # inhibition_i = ι · a_i · rate
REFRACTORY_MIN = 120.0       # after a firing, the coalition is held down for 2 h
REFRACTORY_RATE = 0.08

# coupling of drives to nodes (Σ_k c_ik · x_k)
COUPLE_SOCIAL_USER = 0.02    # social need -> the user node
COUPLE_CURIOSITY_QUESTIONS = 0.012   # curiosity -> open questions
COUPLE_GOAL_INTENTIONS = 0.012       # goal tension -> open intentions
COUPLE_UNCERTAINTY_TRACES = 0.008    # uncertainty -> traces in conflict

# external input
MSG_KICK = 0.6               # a message: a += 0.6 · (cos − 0.35) / 0.65 to similar nodes (other than V1 memories)
QUERY_KICK = 0.8             # ...and V1 memories get 0.8 · score / best score through all of V1's search channels
QUERY_TOP = 30               # (meaning, words, names, "yesterday", links: tuning log, entry 8)
USER_KICK = 0.5              # ...and to the user node
DUE_KICK = 0.9               # a due intention (at a firing or a message)
RECALL_PREVIEW_MIN = 3       # recall ranks by the field after the message's input has spread this long

# intrusions (§6.2, T47–T52)
INTRUSION_RATE_PER_H = 1 / 3  # × (1 + 2·boredom) × (1 − focus)
INTRUSION_KICK = 0.6
INTRUSION_MIN_AGE_H = 24.0   # "old" nodes only
INTRUSION_MARK_MIN = 90.0    # how long a node stays "came to mind for no clear reason"

# ---------- creation: salience (§6.8, T37) ----------
SALIENCE_WEIGHTS = {"novelty": 1.0, "valence": 1.0, "arousal": 1.0, "goal": 1.0, "pe": 1.5, "recurrence": 0.5,
                    "self": 0.5}
RECURRENCE_COS = 0.6
RECURRENCE_DAYS = 7
RECURRENCE_FULL = 3          # this many similar recent nodes = 1
A0_BASE, A0_GAIN = 0.25, 0.5  # initial activation = 0.25 + 0.5 · salience (own nodes × OWN_INPUT on top)
SALIENT_USES = 2             # extra base-level uses at creation = round(salience · 2)

# ---------- learning (§6.8) ----------
BASE_DECAY = 0.5             # B = ln Σ t_k^(−0.5), t in hours
USE_THRESHOLD = 0.5          # a use is recorded when activation crosses this upward...
USE_REPEAT_MIN = 60.0        # ...and again every hour it stays above
USES_KEPT = 64               # the oldest uses beyond this are dropped (their t^−0.5 is negligible)
BASE_EVERY_STEPS = 30        # base levels are recomputed every 30 steps (they change slowly)
HEBB_ETA = 0.002             # Δw = η · a_i · a_j · (1 − w) − λ · w, per minute, over co-active working-memory nodes
                             # (0.02 and no (1 − w) in the spec: edges saturated within an evening; entry 8)
HEBB_LAMBDA = 1e-5           # every edge fades without use (half-life ≈ 48 days)
HEBB_NEW_AFTER_MIN = 10.0    # nodes co-active this long get an edge
HEBB_NEW_W = 0.1
EDGE_PRUNE = 0.01            # learned edges below this are removed
PE_SALIENCE = True           # |PE| enters salience (weight above)
PE_AROUSAL = 0.3             # arousal += 0.3 · |PE|
PE_CURIOSITY = 0.3
PE_FRUSTRATION = 0.5         # frustration += 0.5 · max(0, −PE)
PRAISE_RELIEF = 0.3          # frustration −= 0.3 · positive signal
PE_EDGE_GAIN = 0.5           # a trace's edges × (1 + 0.5 · |PE|)
TRACE_MIN_SIGNAL = 0.2       # a reaction becomes a trace if |signal| ≥ 0.2 ...
TRACE_MIN_PE = 0.3           # ... or it was surprising
RECONSOLIDATION = 0.05       # each recall moves a node's valence 5% toward the current mood

# ---------- drives (§6.3) ----------
# baselines; valence's baseline is the temperament
DRIVE_BASE = {"S": 0.2, "arousal": 0.3, "valence": 0.2, "mood": 0.2, "fatigue": 0.0, "curiosity": 0.3,
              "boredom": 0.1, "social": 0.2, "uncertainty": 0.0, "goal_tension": 0.0, "frustration": 0.0,
              "dissonance": 0.0}
MINIMAL_DRIVES = ("S", "arousal", "social")
S_RISE_TAU_H = 18.0          # sleep pressure rises toward 1 while awake (≈ 0.65 after 16 h)...
S_FALL_TAU_H = 4.0           # ...and falls while asleep
CIRCADIAN_PEAK_H = 17.0      # C = 0.5 + 0.5·cos(2π(h − 17)/24)
AROUSAL_TAU = 30.0
AROUSAL_ASLEEP = 0.1         # arousal's baseline asleep
AROUSAL_MESSAGE = 0.25       # a message: arousal += 0.25 · (1 − arousal)
AROUSAL_SALIENCE = 0.2       # a salient new node: += 0.2 · max(0, salience − 0.5)
AROUSAL_APPRAISAL = 0.5      # toward the appraisal's arousal
VALENCE_HALF_MIN = 20.0      # fast valence relaxes to the mood (V3 affect)
MOOD_HALF_DAYS = 7.0         # mood relaxes to the temperament
FATIGUE_TAU = 240.0          # awake: thinking tires slowly away (60 min in the spec; tuning log, entry 5)...
FATIGUE_TAU_ASLEEP = 60.0    # ...and sleep clears it
FATIGUE_PER_FIRING = 0.3
FATIGUE_BRAKE_GAIN = 2.0     # brake × (1 + 2·fatigue): repeated thinking closes the gate (instead of hard caps)
CURIOSITY_TAU = 720.0
CURIOSITY_PER_QUESTION = 0.0003      # sustained, per open question, per minute
CURIOSITY_RESOLVED = 0.15
BOREDOM_RISE_MIN = 360.0     # rises over 6 h of low novelty and low field activity
BOREDOM_NOVELTY_DROP = 0.5   # novel input: boredom −= 0.5 · novelty
SOCIAL_SATURATE_MIN = 2160.0  # social need saturates over 36 h of silence (awake)
SOCIAL_CONVERSATION_TAU = 30.0  # in conversation it falls back, × (1 + engagement)
UNCERTAINTY_TAU = 120.0
UNCERTAINTY_EDGE = 0.15      # traces count as "the same kind of situation" over edges ≥ this
FRUSTRATION_TAU = 360.0
FRUSTRATION_BLOCKED = 0.3    # a thought it wanted to say and couldn't
FRUSTRATION_UNANSWERED_H = 12.0  # a message written first, unanswered for this long...
FRUSTRATION_UNANSWERED = 0.0005  # ...adds this per minute
DISSONANCE_TAU = 1440.0
DRIVE_NOISE = 0.002          # σ per √minute
THOUGHT_DRIVE_WEIGHT = 1 / 3  # an own thought's feeling moves drives at 1/3 (§4.3)
# couplings W[x][y]: dx/dt += W · y (per minute); the loops of §6.3
COUPLING = {
    "arousal": {"S": -0.004, "frustration": 0.004, "valence": -0.002},
    "valence": {"frustration": -0.01},
    "curiosity": {"boredom": 0.0005, "uncertainty": 0.0005},
    "boredom": {"curiosity": -0.002},
}
# words for the prompt: a drive is mentioned only this far from its baseline (D7)
SALIENT_DRIVE = 0.25

# ---------- attention (§6.4) ----------
WM_SIZE = 12                 # (7 in the spec: tuning log, entry 8)
WM_THRESHOLD = 0.35
COALITION_EDGE = 0.15
FOCUS_DWELL_TAU = 20.0
FOCUS_DECAY_TAU = 20.0       # × (1 + arousal)
FOCUS_SAME = 0.5             # Jaccard at which a coalition is "the same" one

# ---------- gate (§6.5) ----------
COHERENCE_THETA = 0.10       # θ_c × (1 − 0.5·boredom)
COHERENCE_BOREDOM = 0.5
STABILITY_WINDOW_MIN = 15
URGENCY_TAU = 180.0          # τ_u = 3 h
URGENCY_WEIGHTS = {"goal": 0.02, "social": 0.02, "curiosity": 0.02, "uncertainty": 0.02, "dissonance": 0.02,
                   "affect": 0.02, "fresh": 0.02}
URGENCY_FLOORS = {"goal": 0.05, "social": 0.15, "curiosity": 0.05, "uncertainty": 0.1, "dissonance": 0.1,
                  "affect": 0.15, "fresh": 0.2}
SOCIAL_SELF = 0.5            # social source = social · max(a(user), 0.5 · social) (tuning log, entry 4)
URGENCY_MIN_KINDS = 2        # a source counts only while ≥ 2 kinds are above their floors (T122, T125)
FRESH_HOURS = 6.0            # "fresh input" in the coalition: external nodes this young
BRAKE_B0 = 1.0               # brake = b₀ · (1 + 2·fatigue) · (1 + S) · mode_factor
SPEECH_MARGIN = 0.6          # writing first needs u ≥ brake · (1 + 0.6) (0.3 in the spec; tuning log, entry 3)
# Speaking first (tuning log, entry 5): no hard caps; the wish to speak against a threshold that rises with
# shyness and night and falls when the user is there.
#   speech = max u over the last hour / brake + social · a(user) (+ 1 for a due intention)
#   need   = 1 + margin + 0.5·unanswered + 0.3·written today + 1·night − 0.6·present,  night = (0.3 − C)/0.3 ≥ 0
#            (0 from about 10:00 to 23:30, 0.5 at 02:00 and 08:00, 1 at 05:00)
SPEECH_PEAK_MIN = 60.0
SPEECH_SOCIAL = 1.0
SPEECH_DUE = 1.0
SHY_UNANSWERED = 0.5         # per message written first and not answered yet
SHY_TODAY = 0.3              # per message written first today
SPEECH_NIGHT = 1.0           # × night
NIGHT_C = 0.3
PRESENCE_SPEECH = 0.6        # the user has the chat open
PRESENCE_MIN = 15.0          # opening the chat counts as presence this long
EMERGENCY_PER_DAY = 30       # the only hard limit: gate firings + dreams per sim day, against runaway cost;
                             # hitting it is logged and shown in the chat, never part of the dynamics

# Waking (tuning log, entry 5): waking up, and coming to when the program starts, are a burst, not a slow start
WAKE_AROUSAL = 0.3           # arousal += 0.3
WAKE_URGENCY = 0.6           # u += 0.6 · b₀: waking is a pulse into urgency too...
PRESENCE_URGENCY = 0.6       # ...and so is the user arriving
WAKE_UNFINISHED = 0.5        # open intentions and questions get this...
WAKE_RECENT = 0.4            # ...and the most salient nodes of the last 3 days this
WAKE_RECENT_N = 5
WAKE_RECENT_DAYS = 3.0
ABSENCE_MIN = 10.0           # chat: the program was off longer than this = absence (no thoughts, no messages),
                             # lived quietly as sleep, then a waking burst
NEAR_MISS_MIN_GAP = 30.0     # a near-miss is logged at most every 30 min per kind

# ---------- sleep as a mode (§6.10) ----------
SLEEP_K = 1 / 30             # p = dt · k · sigmoid((S − C − θ − 0.5·arousal − SLEEP_URGENCY·u) / T)
SLEEP_THETA = 0.3            # (0.1 in the spec; tuning log, entries 0 and 1)
SLEEP_T = 0.05
SLEEP_URGENCY = 0.2          # the urgency term: −0.5·u in the spec (tuning log, entry 2)
WAKE_S = 0.15                # waking when S < θ_wake and C is rising
CYCLE_MIN = 90.0
REM_SHARE_FIRST, REM_SHARE_STEP, REM_SHARE_MAX = 0.15, 0.1, 0.5
NREM = {"input": 0.2, "spread": 0.5, "noise": 0.5, "inhibition": 1.0}
REM = {"input": 0.2, "spread": 1.0, "noise": 2.0, "inhibition": 0.5}
REM_WEAK_EDGE, REM_WEAK_GAIN = 0.2, 2.0   # edges under 0.2 count double in REM
REM_THETA_GAIN = 1.5
DREAMS_PER_NIGHT = 2
REPLAY_EVERY_MIN = 5.0       # NREM: one of the day's nodes every 5 min...
REPLAY_KICK = 0.5            # ...gets this
NREM_HEBB_GAIN = 3.0
NREM_WEAK_EDGE, NREM_WEAK_DECAY = 0.05, 5.0
DUPLICATE_COS = 0.82         # near-duplicates get a strong edge and pool their base level
DUPLICATE_W = 0.9
BRAKE_MODE = {"awake": 1.0, "rem": 1.0}   # NREM and conversation: the gate is closed

# ---------- episodic memory (tuning log, entry 8) ----------
PASSAGE_CHARS = 800          # a user message this long is a passage (a text shared), not just a remark
PASSAGE_MAX_PARAGRAPHS = 40
VERBATIM_CHARS = 700         # what stays word for word of a charged passage
VERBATIM_AROUSAL = 0.5       # a passage is charged if the moment's arousal reached this...
VERBATIM_VALENCE = 0.5       # ...or |valence| this
EVENT_TEXT_CHARS = 200
EVENT_REPLY_CHARS = 140
EVENT_CHAIN_W = 0.4          # an event to the next one (0.2 across conversations)
EVENT_FACT_W = 0.5           # an event to the facts extracted from it
EVENT_MIN_A = 0.2            # events at least this active can be shown...
EVENTS_ACTIVE = 4            # ...the 4 most active, each with its neighbours
EVENTS_LAST = 5              # at the start of a conversation (or "where did we stop?"): how the last one ended
EVENTS_SHOWN = 12
EVENTS_BUDGET = 4000         # characters for the whole section; the oldest go first
EVENT_TIME_KICK = 0.5        # events in a date range named in the message ("yesterday")

# ---------- grip (tuning log, entry 6) ----------
GRIP_MEMORY_COS = 0.58       # a reference counts as anchored if the message is this close to something remembered
GRIP_GUESS_COS = 0.50        # ...half-anchored (a guess, "if you mean…") from this close (bge-m3: unrelated ≈ 0.40-0.47)
GRIP_GUESS_A = 0.45          # a pointer's guess: the most active remembered node, if at least this active
GRIP_SHORT_WORDS = 10        # a message this short has no room for a pointer's antecedent
GRIP_PER_ISSUE = 0.4         # grip = 1 − 0.4 per issue (0.2 for a guess)
GRIP_UNCERTAINTY = 0.3       # uncertainty += 0.3 · (1 − grip)

# ---------- verbalization, traces, recall, narrative ----------
TRACES_SHOWN = 4
TRACE_REPLY_CHARS = 600
TRACE_TEXT_CHARS = 300
RECALL_LIMIT = 12
RECALL_BASE_WEIGHT = 0.3     # rank = a + 0.3 · σ(B)
RECALL_MIN = 0.15
DISSONANCE_TRACES = 6
COALITION_SHOWN = 8
