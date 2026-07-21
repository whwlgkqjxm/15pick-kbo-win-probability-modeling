# Training-Strategy Comparison

**Question:** Which temporal learning strategy is most stable under seasonal drift?

**Result:** The most recent 720 eligible games with L2 logistic regression produced the strongest observed 2026 development result. Daily and online refits did not improve probability quality.

**Decision:** Freeze the recent-720 model as a development candidate and require prospective confirmation.
