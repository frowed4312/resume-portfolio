use std::{env, net::{IpAddr, SocketAddr, TcpStream}, time::Duration};

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 { return Err("Usage: tcp-probe IP PORTS TIMEOUT_MS".into()); }
    let ip: IpAddr = args[1].parse().map_err(|_| "Invalid IP")?;
    let ports: Vec<u16> = args[2].split(',').map(|p| p.parse::<u16>().map_err(|_| "Invalid port"))
        .collect::<Result<_, _>>()?;
    let timeout: u64 = args[3].parse().map_err(|_| "Invalid timeout")?;
    if ports.is_empty() || ports.len() > 1024 || ports.contains(&0) || !(50..=10000).contains(&timeout) {
        return Err("Ports must be 1..65535, max 1024; timeout 50..10000ms".into());
    }
    // Python owns bounded host concurrency; this worker avoids nested thread explosion.
    for port in ports {
        if TcpStream::connect_timeout(&SocketAddr::new(ip, port), Duration::from_millis(timeout)).is_ok() {
            println!("{}", port);
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() { eprintln!("{}", error); std::process::exit(2); }
}
