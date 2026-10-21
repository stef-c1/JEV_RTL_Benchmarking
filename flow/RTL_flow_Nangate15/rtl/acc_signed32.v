// Signed 32-bit accumulator with an enable and a synchronous clear.
//
// A leaf module of mac_int8. It adds the 16-bit addend to the sum when
// en_i is high, and holds the sum when en_i is low. clr_i clears the sum
// on the next rising edge and wins over en_i. rst_n clears it at once.
// The sum wraps on overflow.

module acc_signed32 (
    input  wire               clk_i,
    input  wire               rst_n,
    input  wire               en_i,
    input  wire               clr_i,
    input  wire signed [15:0] addend_i,
    output reg  signed [31:0] sum_o
);

    always @(posedge clk_i or negedge rst_n) begin
        if (!rst_n)
            sum_o <= 32'sd0;
        else if (clr_i)
            sum_o <= 32'sd0;
        else if (en_i)
            sum_o <= sum_o + addend_i;
    end

endmodule
