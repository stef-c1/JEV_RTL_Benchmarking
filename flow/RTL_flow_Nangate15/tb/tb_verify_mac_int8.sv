// Verification testbench for mac_int8.
//
// Steps 1 and 3 run this file. Step 1 compiles it with the RTL, step 3
// with the gate-level netlist. The step passes only when this file prints
// "ALL TESTS PASSED".
//
// tb/test_mac_int8.py checks the same behavior with cocotb.

`timescale 1ns/1ps

`ifndef CLK_PERIOD_NS
  `define CLK_PERIOD_NS 2.0
`endif

module tb_verify_mac_int8;

    localparam real CLK_HALF = `CLK_PERIOD_NS / 2.0;

    logic               clk_i;
    logic               rst_n;
    logic               en_i;
    logic               clr_i;
    logic signed [7:0]  a_i;
    logic signed [7:0]  b_i;
    logic signed [31:0] acc_o;

    // The instance name must match DUT_INSTANCE in the configuration.
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

    int                 pass_count;
    int                 fail_count;
    logic signed [31:0] expected;
    int                 i;

    task automatic check(input logic signed [31:0] want, input int line);
        if (acc_o === want) begin
            pass_count++;
        end else begin
            fail_count++;
            $display("FAIL (line %0d): acc_o expected=%0d got=%0d", line, want, acc_o);
        end
    endtask

    // One operation, then the check.
    task automatic step(input logic signed [7:0] a,
                        input logic signed [7:0] b,
                        input logic              en,
                        input logic              clr);
        a_i   = a;
        b_i   = b;
        en_i  = en;
        clr_i = clr;
        @(posedge clk_i);
        #(CLK_HALF / 2.0);
    endtask

    initial begin
        pass_count = 0;
        fail_count = 0;
        expected   = 32'sd0;

        // Drive every input before the reset ends.
        rst_n = 1'b0;
        en_i  = 1'b0;
        clr_i = 1'b0;
        a_i   = 8'sd0;
        b_i   = 8'sd0;
        repeat (4) @(posedge clk_i);
        rst_n = 1'b1;
        @(posedge clk_i);
        #(CLK_HALF / 2.0);
        check(32'sd0, `__LINE__);

        // The corner values of the signed multiplier.
        step(  8'sd1,   8'sd1,  1'b1, 1'b0); expected += 32'sd1;     check(expected, `__LINE__);
        step( -8'sd1,   8'sd1,  1'b1, 1'b0); expected += -32'sd1;    check(expected, `__LINE__);
        step(  8'sd127, 8'sd127, 1'b1, 1'b0); expected += 32'sd16129; check(expected, `__LINE__);
        step( -8'sd128, -8'sd128, 1'b1, 1'b0); expected += 32'sd16384; check(expected, `__LINE__);
        step( -8'sd128,  8'sd127, 1'b1, 1'b0); expected += -32'sd16256; check(expected, `__LINE__);

        // Random operands.
        for (i = 0; i < 200; i++) begin
            automatic logic signed [7:0] ra = 8'($urandom);
            automatic logic signed [7:0] rb = 8'($urandom);
            step(ra, rb, 1'b1, 1'b0);
            expected += 32'(ra) * 32'(rb);
            check(expected, `__LINE__);
        end

        // A low enable holds the value.
        for (i = 0; i < 8; i++) begin
            step(8'($urandom), 8'($urandom), 1'b0, 1'b0);
            check(expected, `__LINE__);
        end

        // The clear wins over the enable.
        step(8'sd7, 8'sd7, 1'b1, 1'b1);
        expected = 32'sd0;
        check(expected, `__LINE__);

        step(8'sd2, 8'sd3, 1'b1, 1'b0);
        expected = 32'sd6;
        check(expected, `__LINE__);

        $display("--------------------------------------------------");
        $display("Verification complete: PASS=%0d  FAIL=%0d", pass_count, fail_count);
        if (fail_count == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAILURES DETECTED");
        $display("--------------------------------------------------");
        $finish;
    end

    // The watchdog stops a testbench that hangs.
    initial begin
        #(CLK_HALF * 2 * 5000);
        $display("TIMEOUT");
        $finish;
    end

endmodule
