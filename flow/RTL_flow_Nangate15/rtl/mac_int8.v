// Signed 8-bit multiply-accumulate unit. The top module of the example.
//
// acc_o = acc_o + a_i * b_i on a rising clock edge when en_i is high.
// clr_i clears the accumulator on the next rising edge, and rst_n clears
// it at once. The accumulator wraps on overflow.
//
// The design is three files, to show how a hierarchy is built:
//
//   mac_int8            this file, the top module
//     mult_signed8      rtl/mult_signed8.v
//     acc_signed32      rtl/acc_signed32.v
//
// RTL_FILES in config.sh lists the two leaf modules first and this file
// last, because a module must be read after the modules it uses.

module mac_int8 (
    input  wire               clk_i,
    input  wire               rst_n,
    input  wire               en_i,
    input  wire               clr_i,
    input  wire signed [7:0]  a_i,
    input  wire signed [7:0]  b_i,
    output wire signed [31:0] acc_o
);

    wire signed [15:0] product;

    mult_signed8 u_mult (
        .a_i (a_i),
        .b_i (b_i),
        .p_o (product)
    );

    acc_signed32 u_acc (
        .clk_i    (clk_i),
        .rst_n    (rst_n),
        .en_i     (en_i),
        .clr_i    (clr_i),
        .addend_i (product),
        .sum_o    (acc_o)
    );

endmodule
