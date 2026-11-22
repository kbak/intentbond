#[cfg(test)]
mod tests {
    // [utest~addition~1->req~increment~1] ib-cargo execution-example tests::round_trip
    #[test]
    fn round_trip() {
        assert_eq!(1_i32.checked_add(1), Some(2));
    }
}
