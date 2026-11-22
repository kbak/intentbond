use vstd::prelude::*;

verus! {
    // [proof~increment~1->req~increment~1] ib-verus arithmetic::increment
    pub proof fn increment(n: int) ensures n + 1 > n {}

    pub proof fn sibling(n: int) ensures n + 2 > n {}
}
