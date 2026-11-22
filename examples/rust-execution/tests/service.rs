mod tests {
    use std::io::{BufRead, BufReader};
    use std::net::TcpStream;

    // [utest~service~1->req~readiness~1] ib-cargo execution-example::service tests::round_trip
    #[test]
    #[ignore = "requires an externally provisioned readiness service"]
    fn round_trip() {
        let address = std::env::var("EXAMPLE_READY_ADDR").expect("provide a readiness service");
        let mut stream = BufReader::new(TcpStream::connect(address).unwrap());
        let mut line = String::new();
        stream.read_line(&mut line).unwrap();
        assert_eq!(line, "ready\n");
    }
}
