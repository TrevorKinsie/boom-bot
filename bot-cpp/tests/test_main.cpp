#include "tests.h"

#include "bb_config.h"
#include "bb_log.h"

int main() {
    bb::cfg::load_config();
    bb::log::set_error_log_path(""); // keep test output clean
    return bbtest::run_all();
}