// Signed 8-bit multiplier.
//
// A leaf module of mac_int8. Both operands are two's complement, so the
// product needs 16 bits: -128 x -128 is +16384.
//
// RTL_FILES in config.sh lists this file before mac_int8.v, because
// mac_int8 uses it.

module mult_signed8 (
    input  wire signed [7:0]  a_i,
    input  wire signed [7:0]  b_i,
    output wire signed [15:0] p_o
);

    assign p_o = a_i * b_i;

endmodule
