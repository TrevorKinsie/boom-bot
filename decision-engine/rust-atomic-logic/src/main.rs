//! Atomic-logic CLI bridge.
//!
//! Reads a single JSON request line from standard input, invokes the
//! corresponding pure atomic primitive, and writes a single JSON result line to
//! standard output. The protocol is deliberately line-delimited JSON so that
//! the Java middleware can host it as a short-lived subprocess (one decision
//! per process), mirroring the UCI-style engine invocation used elsewhere in
//! boom-bot.
//!
//! Request (one JSON object per line):
//!
//! ```json
//! {"kind":"ROULETTE_SPIN","seed":"a1b2c3","params":{"min":0,"max":37}}
//! ```
//!
//! Response:
//!
//! ```json
//! {"ok":true,"kind":"ROULETTE_SPIN","value":17,"raw":1234567890123}
//! ```

use std::io::{self, BufRead, Write};

use atomic_logic::{
    atomic_fairness_hash, atomic_roll_craps, atomic_spin_roulette, atomic_zeus_grid,
    seed_from_hex, splitmix64,
};

/// Extract the value of a JSON string field from a flat JSON object string.
fn json_str_field(json: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":");
    let start = json.find(&needle)?;
    let value_start = start + needle.len();
    let rest = &json[value_start..];
    let rest = rest.trim_start();
    let rest = rest.strip_prefix('"')?;
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

/// Extract the value of a JSON integer/number field from a flat JSON object.
fn json_num_field(json: &str, key: &str) -> Option<i64> {
    let needle = format!("\"{key}\":");
    let start = json.find(&needle)?;
    let value_start = start + needle.len();
    let rest = &json[value_start..];
    let rest = rest.trim_start();
    let end = rest
        .find(|c: char| !(c.is_ascii_digit() || c == '-' || c == '.'))
        .unwrap_or(rest.len());
    rest[..end].parse::<f64>().ok().map(|f| f as i64)
}

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    let mut line = String::new();

    // Read exactly one request line (the Java middleware spawns one process
    // per decision and closes stdin afterwards).
    if stdin.lock().read_line(&mut line).is_err() || line.trim().is_empty() {
        let _ = writeln!(stdout, "{{\"ok\":false,\"error\":\"empty_request\"}}");
        let _ = stdout.flush();
        return;
    }

    let request = line.trim();
    let kind = json_str_field(request, "kind").unwrap_or_default();
    let seed_hex = json_str_field(request, "seed").unwrap_or_default();
    let seed = seed_from_hex(&seed_hex);

    let response = dispatch(&kind, seed, request);
    let _ = writeln!(stdout, "{response}");
    let _ = stdout.flush();
}

fn dispatch(kind: &str, seed: u64, request: &str) -> String {
    match kind {
        "ROULETTE_SPIN" => {
            let value = atomic_spin_roulette(seed);
            format!(
                "{{\"ok\":true,\"kind\":\"ROULETTE_SPIN\",\"value\":{value},\"raw\":{}}}",
                splitmix64(seed)
            )
        }
        "CRAPS_ROLL" => {
            let (die1, die2) = atomic_roll_craps(seed);
            format!(
                "{{\"ok\":true,\"kind\":\"CRAPS_ROLL\",\"value\":{},\"die1\":{die1},\"die2\":{die2},\"raw\":{}}}",
                die1 + die2,
                splitmix64(seed)
            )
        }
        "ZEUS_SPIN" => {
            let rows = json_num_field(request, "rows").unwrap_or(5) as u64;
            let cols = json_num_field(request, "cols").unwrap_or(5) as u64;
            let grid = atomic_zeus_grid(seed, rows, cols);
            let indices: Vec<String> = grid.iter().map(|i| i.to_string()).collect();
            format!(
                "{{\"ok\":true,\"kind\":\"ZEUS_SPIN\",\"value\":{},\"symbols\":[{}],\"raw\":{}}}",
                rows * cols,
                indices.join(","),
                splitmix64(seed)
            )
        }
        "FAIRNESS_HASH" => {
            let hash = atomic_fairness_hash(seed);
            format!("{{\"ok\":true,\"kind\":\"FAIRNESS_HASH\",\"value\":{seed},\"hash\":\"{hash}\"}}")
        }
        _ => format!("{{\"ok\":false,\"error\":\"unsupported_kind:{kind}\"}}"),
    }
}
