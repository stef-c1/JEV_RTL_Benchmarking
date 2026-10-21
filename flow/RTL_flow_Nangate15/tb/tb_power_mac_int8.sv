// Power testbench for mac_int8.
//
// Step 4 runs this file on the gate-level netlist. The VCD file it writes
// is the switching activity that PrimeTime turns into a power number, so
// the stimulus below is the workload whose power you measure.
//
// The flow sets CLK_PERIOD_NS from config.sh, and runs the simulator
// inside results/4_power/, where the VCD file lands.

`timescale 1ns/1ps

`ifndef CLK_PERIOD_NS
  `define CLK_PERIOD_NS 2.0
`endif

module tb_power_mac_int8;

    localparam real CLK_HALF = `CLK_PERIOD_NS / 2.0;

    logic               clk_i;
    logic               rst_n;
    logic               en_i;
    logic               clr_i;
    logic signed [7:0]  a_i;
    logic signed [7:0]  b_i;
    logic signed [31:0] acc_o;

    // The instance name must match DUT_INSTANCE in config.sh.
    mac_int8 dut (
        .clk_i (clk_i),
        .rst_n (rst_n),
        .en_i  (en_i),
        .clr_i (clr_i),
        .a_i   (a_i),
        .b_i   (b_i),
        .acc_o (acc_o)
    );

    initial clk_i = 1'b0;
    always #(CLK_HALF) clk_i = ~clk_i;

    int i;

    initial begin
        // Drive every input, then let the design settle before the dump
        // starts. Activity from the reset would bias the power number.
        rst_n = 1'b0;
        en_i  = 1'b0;
        clr_i = 1'b0;
        a_i   = 8'sd0;
        b_i   = 8'sd0;
        repeat (4) @(posedge clk_i);
        rst_n = 1'b1;
        repeat (4) @(posedge clk_i);

        $dumpfile("power.vcd");
        $dumpvars(0, tb_power_mac_int8);

        // High activity: random signed operands, accumulating every cycle.
        en_i = 1'b1;
        for (i = 0; i < 256; i++) begin
            a_i = 8'($urandom);
            b_i = 8'($urandom);
            @(posedge clk_i);
        end

        // Medium activity: a sign-alternating ramp.
        for (i = 0; i < 64; i++) begin
            a_i = 8'(i) - 8'sd32;
            b_i = 8'sd32 - 8'(i);
            @(posedge clk_i);
        end

        // The accumulator clears, then restarts.
        clr_i = 1'b1;
        @(posedge clk_i);
        clr_i = 1'b0;

        // Low activity: the operands hold and the enable is low, so only
        // the clock network toggles.
        a_i  = 8'sd17;
        b_i  = -8'sd23;
        en_i = 1'b0;
        repeat (64) @(posedge clk_i);

        $finish;
    end

endmodule
