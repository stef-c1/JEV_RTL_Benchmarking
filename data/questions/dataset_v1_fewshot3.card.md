# Data card: dataset_v1_fewshot3

Dataset v1 with three solved examples in the state of each request (harness/fewshot.py, MV 2026-10-16).

- Source: `data/questions/dataset_v1.jsonl`, SHA-256 96814ea63d89b98af7f87c5f6d8e5fe0f35ec710c30755c9d0723fbec4ddbe2a, the question file of the four Kev runs of 2026-10-15.
- Split: test only. The examples are development designs, and the split is per base design. No example implements the function (top module, or VerilogEval problem) of a test design.
- Requests: 725, one question each. Questions per key: {'compiles': 123, 'synthesizes': 123, 'slack': 92, 'reach': 92, 'area': 92, 'power': 85, 'reason': 16, 'smaller_area': 46, 'lower_power': 44, 'higher_reach': 12}.
- The questions and the correct answers are those of the test split of dataset v1. The state of each request is the state of its dataset v1 request, with one new field before the other fields: `examples`. A pair question gets the examples of its metric, without the levels.

Kev input tokens, exact (probes/kev_token_count.py):

| Request | Question | Example set | Requests | Median | Maximum | Above 8,192 |
|---|---|---|---|---|---|---|
| basic | compiles | compile | 123 | 1,378 | 6,515 | 0 |
| basic | synthesizes | synth | 123 | 1,238 | 6,375 | 0 |
| performance | slack | slack | 92 | 2,463 | 8,607 | 1 |
| performance | reach | reach | 92 | 1,967 | 8,111 | 0 |
| performance | area | area | 92 | 2,082 | 8,226 | 1 |
| performance | power | power | 85 | 2,424 | 8,534 | 1 |
| reason | reason | reason | 16 | 1,607 | 6,769 | 0 |
| pair | smaller_area | area | 46 | 2,475 | 4,177 | 0 |
| pair | lower_power | power | 44 | 2,814 | 4,514 | 0 |
| pair | higher_reach | reach | 12 | 2,424 | 2,523 | 0 |

## The examples

The text of the field `examples`, as the model reads it.

### compile

Questions: ['compiles']. Designs: ['metrex_05095', 'mut_illegal_code_1_metrex_05095', 'revold_rtllm_Prob001_accu_650a52a44963']

```text
Three solved examples: three other designs, each with the result of the simulator compiler in `tool`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d;
		end
	end
endmodule
Correct answer: yes. vlog reports no error.

Example 2. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d_x;
		end
	end
endmodule
Correct answer: no. vlog reports at least one error. The first error: ** Error: rtl/metrex_05095.v(21): (vlog-2730) Undefined variable: 'd_x'.

Example 3. Top module accu. RTL:
// ---- file: Prob001_accu.sv ----
module accu(
    input clk,
    input rst_n,
    input [7:0] data_in,
    input valid_in,
    output valid_out,
    output [9:0] data_out
);

reg [1:0] counter;
reg [9:0] sum;
reg [9:0] data_out_reg;
reg valid_out_reg;

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        counter <= 2'b00;
        sum <= 10'b0;
        data_out_reg <= 10'b0;
        valid_out_reg <= 1'b0;
    end else begin
        if (valid_in) begin
            if (counter == 2'b11) begin
                counter <= 2'b00;
                sum <= 10'b0;
                data_out_reg <= sum;
                valid_out_reg <= 1'b1;
            end else begin
                sum <= sum + data_in;
                counter <= counter + 1'b1;
                valid_out_reg <= 1'b0;
            end
        end else begin
            valid_out_reg <= 1'b0;
        end
    end
end

always @(posedge clk) begin
    data_out <= data_out_reg;
    valid_out <= valid_out_reg;
end

endmodule
Correct answer: no. vlog reports at least one error. The first error: ** Error: rtl/Prob001_accu.sv(40): (vlog-2110) Illegal reference to net "data_out".

```

### synth

Questions: ['synthesizes']. Designs: ['ve_Prob084_ece241_2013_q12', 'mut_multiple_drivers_0_ve_Prob084_ece241_2013_q12', 'mut_illegal_code_1_metrex_05095']

```text
Three solved examples: three other designs, each with the result of the synthesis tool in `tool`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Correct answer: yes. The tool finishes with no error, every module instance is resolved, and every register maps to a library cell.

Example 2. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];


  always @(posedge clk) q <= q;
endmodule
Correct answer: no. The tool stops with an error. The first error: Error: rtl/Prob084_ece241_2013_q12.sv:21: Net 'q[7]' or a directly connected net is driven by more than one source, and not all drivers are three-state. (ELAB-366)

Example 3. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d_x;
		end
	end
endmodule
Correct answer: no. The tool stops with an error. The first error: Error: rtl/metrex_05095.v:21: The symbol 'd_x' is not defined. (VER-956)

```

### reason

Questions: ['reason']. Designs: ['mut_multiple_drivers_0_ve_Prob084_ece241_2013_q12', 'mut_illegal_code_1_metrex_05095', 'mut_event_list_0_ve_Prob096_review2015_fsmseq']

```text
Three solved examples: three other designs that the synthesis tool in `tool` does not synthesize, each with the reason. The question is about the design in `rtl`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];


  always @(posedge clk) q <= q;
endmodule
Correct answer: multiple_drivers. The first error: Error: rtl/Prob084_ece241_2013_q12.sv:21: Net 'q[7]' or a directly connected net is driven by more than one source, and not all drivers are three-state. (ELAB-366)

Example 2. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d_x;
		end
	end
endmodule
Correct answer: illegal_code. The first error: Error: rtl/metrex_05095.v:21: The symbol 'd_x' is not defined. (VER-956)

Example 3. Top module RefModule. RTL:
// ---- file: Prob096_review2015_fsmseq.sv ----

module RefModule (
  input clk,
  input reset,
  input data,
  output start_shifting
);

  parameter S=0, S1=1, S11=2, S110=3, Done=4;

  reg [2:0] state, next;

  always_comb begin
    case (state)
      S: next = data ? S1: S;
      S1: next = data ? S11: S;
      S11: next = data ? S11 : S110;
      S110: next = data ? Done : S;
      Done: next = Done;
    endcase
  end

  always @(posedge clk or negedge clk)
    if (reset) state <= S;
    else state <= next;

  assign start_shifting = state == Done;

endmodule
Correct answer: event_list. The first error: Error: rtl/Prob096_review2015_fsmseq.sv:23: Events that depend on two edges of the same variable are not supported by synthesis. (ELAB-93)

```

### slack

Questions: ['slack']. Designs: ['rtllm_div_16bit', 'metrex_24768', 've_Prob084_ece241_2013_q12']

```text
Three solved examples: three other designs, each with the exact worst slack after synthesis with the flow in `flow` at the clock in `clock`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module verified_div_16bit. RTL:
// ---- file: verified_div_16bit.v ----
module verified_div_16bit(
    input wire [15:0] A,
    input wire [7:0] B,
    output wire [15:0] result,
    output wire [15:0] odd
    );

reg [15:0] a_reg;
reg [15:0] b_reg;
reg [31:0] tmp_a;
reg [31:0] tmp_b;
integer i;

always@(*) begin
    a_reg = A;
    b_reg = B;
end

always@(*) begin
    begin
        tmp_a = {16'b0, a_reg};
        tmp_b = {b_reg, 16'b0};
        for(i = 0;i < 16;i = i+1) begin
            tmp_a = tmp_a << 1;
            if (tmp_a >= tmp_b) begin
                tmp_a = tmp_a - tmp_b + 1;
            end
            else begin
                tmp_a = tmp_a;
            end
        end
    end
end

assign odd = tmp_a[31:16];
assign result = tmp_a[15:0];

endmodule
Result: worst slack +0.365 ns. Level: 0 ns to 0.5 ns.

Example 2. Top module matrix_mult_N_M_0. RTL:
// ---- file: metrex_24768.v ----

module matrix_mult_N_M_0
#(
	parameter N=3,
	parameter M=32
)
(
	clk,
	rst,
	g_input,
	e_input,
	o
);
	input clk,rst;
	input[M*N*N-1:0] g_input;
	input[M*N*N-1:0] e_input;
	output[M*N*N-1:0] o;

	wire [M-1:0] xij[N-1:0][N-1:0];
	wire [M-1:0] yij[N-1:0][N-1:0];
	wire  [M-1:0] oij[N-1:0][N-1:0];
	wire  [M-1:0] oijk[N-1:0][N-1:0][N-1:0];


	wire  [2*M-1:0] xyijk[N-1:0][N-1:0][N-1:0];

	genvar i;
	genvar j;
	genvar k;

	generate
	for (i=0;i<N;i=i+1)
	begin:ASS_ROW
		for (j=0;j<N;j=j+1)
		begin:ASS_COL
			assign xij[i][j] = g_input[M*(N*i+j+1)-1:M*(N*i+j)];
			assign yij[i][j] = e_input[M*(N*i+j+1)-1:M*(N*i+j)];
			assign o[M*(N*i+j+1)-1:M*(N*i+j)] = oij[i][j];
			assign oijk[i][j][0] = xyijk[i][j][0][M-1:0];
			assign oij[i][j] = oijk[i][j][N-1];
		end
	end
	endgenerate

	generate
	for (i=0;i<N;i=i+1)
	begin:MUL_ROW_MULT
		for (j=0;j<N;j=j+1)
		begin:MUL_COL_MULT
			for (k=0;k<N;k=k+1)
			begin:MULT_O
				assign xyijk[i][j][k] = xij[i][k]*yij[k][j];
			end
		end
	end
	endgenerate

	generate
	for (i=0;i<N;i=i+1)
	begin:MUL_ROW_ADD
		for (j=0;j<N;j=j+1)
		begin:MUL_COL_ADD
			for (k=1;k<N;k=k+1)
			begin:ADD_O
				assign oijk[i][j][k] = xyijk[i][j][k][M-1:0] + oijk[i][j][k-1];
			end
		end
	end
	endgenerate


endmodule
Result: worst slack +0.962 ns. Level: 0.5 ns to 1.0 ns.

Example 3. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: worst slack +1.532 ns. Level: 1.5 ns or more.

```

### reach

Questions: ['reach']. Designs: ['rtllm_div_16bit', 've_Prob084_ece241_2013_q12', 'metrex_05095']

```text
Three solved examples: three other designs, each with the exact reachable clock frequency, 1 / (clock period - worst slack), after synthesis with the flow in `flow` at the clock in `clock`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module verified_div_16bit. RTL:
// ---- file: verified_div_16bit.v ----
module verified_div_16bit(
    input wire [15:0] A,
    input wire [7:0] B,
    output wire [15:0] result,
    output wire [15:0] odd
    );

reg [15:0] a_reg;
reg [15:0] b_reg;
reg [31:0] tmp_a;
reg [31:0] tmp_b;
integer i;

always@(*) begin
    a_reg = A;
    b_reg = B;
end

always@(*) begin
    begin
        tmp_a = {16'b0, a_reg};
        tmp_b = {b_reg, 16'b0};
        for(i = 0;i < 16;i = i+1) begin
            tmp_a = tmp_a << 1;
            if (tmp_a >= tmp_b) begin
                tmp_a = tmp_a - tmp_b + 1;
            end
            else begin
                tmp_a = tmp_a;
            end
        end
    end
end

assign odd = tmp_a[31:16];
assign result = tmp_a[15:0];

endmodule
Result: reachable clock frequency 612 MHz. Level: Below 1 GHz.

Example 2. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: reachable clock frequency 2,137 MHz. Level: 2 GHz to 3 GHz.

Example 3. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d;
		end
	end
endmodule
Result: reachable clock frequency 3,572 MHz. Level: 3 GHz to 4 GHz.

```

### reach (pair questions)

Questions: ['higher_reach']. Designs: ['rtllm_div_16bit', 've_Prob084_ece241_2013_q12', 'metrex_05095']

```text
Three solved examples: three other designs, each with the exact reachable clock frequency, 1 / (clock period - worst slack), after synthesis with the flow in `flow` at the clock in `clock`. The question is about the designs in `rtl_a` and `rtl_b`, not about these examples.

Example 1. Top module verified_div_16bit. RTL:
// ---- file: verified_div_16bit.v ----
module verified_div_16bit(
    input wire [15:0] A,
    input wire [7:0] B,
    output wire [15:0] result,
    output wire [15:0] odd
    );

reg [15:0] a_reg;
reg [15:0] b_reg;
reg [31:0] tmp_a;
reg [31:0] tmp_b;
integer i;

always@(*) begin
    a_reg = A;
    b_reg = B;
end

always@(*) begin
    begin
        tmp_a = {16'b0, a_reg};
        tmp_b = {b_reg, 16'b0};
        for(i = 0;i < 16;i = i+1) begin
            tmp_a = tmp_a << 1;
            if (tmp_a >= tmp_b) begin
                tmp_a = tmp_a - tmp_b + 1;
            end
            else begin
                tmp_a = tmp_a;
            end
        end
    end
end

assign odd = tmp_a[31:16];
assign result = tmp_a[15:0];

endmodule
Result: reachable clock frequency 612 MHz.

Example 2. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: reachable clock frequency 2,137 MHz.

Example 3. Top module dffl_18. RTL:
// ---- file: metrex_05095.v ----

module dffl_18 (
	clk,
	ld,
	rst,
	d,
	q
);
	// synthesis attribute keep_hierarchy dffl_18 "true";
	input clk;
	input ld;
	input rst;
	input [17:0] d;
	output [17:0] q;
	reg [17:0] q;

	always @(posedge clk) begin
		if (rst == 1'b0) begin
			q <= 18'b0;
		end else if (ld == 1'b1) begin
			q <= d;
		end
	end
endmodule
Result: reachable clock frequency 3,572 MHz.

```

### area

Questions: ['area']. Designs: ['ve_Prob084_ece241_2013_q12', 'rtllm_div_16bit', 'metrex_11803']

```text
Three solved examples: three other designs, each with the exact total cell area after synthesis with the flow in `flow` at the clock in `clock`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: total cell area 14.06 um2 = 71.5 GE. Level: Below 100 GE.

Example 2. Top module verified_div_16bit. RTL:
// ---- file: verified_div_16bit.v ----
module verified_div_16bit(
    input wire [15:0] A,
    input wire [7:0] B,
    output wire [15:0] result,
    output wire [15:0] odd
    );

reg [15:0] a_reg;
reg [15:0] b_reg;
reg [31:0] tmp_a;
reg [31:0] tmp_b;
integer i;

always@(*) begin
    a_reg = A;
    b_reg = B;
end

always@(*) begin
    begin
        tmp_a = {16'b0, a_reg};
        tmp_b = {b_reg, 16'b0};
        for(i = 0;i < 16;i = i+1) begin
            tmp_a = tmp_a << 1;
            if (tmp_a >= tmp_b) begin
                tmp_a = tmp_a - tmp_b + 1;
            end
            else begin
                tmp_a = tmp_a;
            end
        end
    end
end

assign odd = tmp_a[31:16];
assign result = tmp_a[15:0];

endmodule
Result: total cell area 260.16 um2 = 1,323.3 GE. Level: 1,000 GE to 10,000 GE.

Example 3. Top module tmu2_dpram. RTL:
// ---- file: metrex_11803.v ----

module tmu2_dpram #(
    parameter depth = 11, 
    parameter width = 32
) (
    input sys_clk,

    input [depth-1:0] ra,
    input re,
    output [width-1:0] rd,

    input [depth-1:0] wa,
    input we,
    input [width-1:0] wd
);

reg [width-1:0] ram[0:(1 << depth)-1];

reg [depth-1:0] rar;

always @(posedge sys_clk) begin
    if(re) begin
        rar <= ra;
    end
    if(we) begin
        ram[wa] <= wd;
    end
end

assign rd = ram[rar];

endmodule
Result: total cell area 102,132.74 um2 = 519,474.0 GE. Level: 100,000 GE or more.

```

### area (pair questions)

Questions: ['smaller_area']. Designs: ['ve_Prob084_ece241_2013_q12', 'rtllm_div_16bit', 'metrex_11803']

```text
Three solved examples: three other designs, each with the exact total cell area after synthesis with the flow in `flow` at the clock in `clock`. The question is about the designs in `rtl_a` and `rtl_b`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: total cell area 14.06 um2 = 71.5 GE.

Example 2. Top module verified_div_16bit. RTL:
// ---- file: verified_div_16bit.v ----
module verified_div_16bit(
    input wire [15:0] A,
    input wire [7:0] B,
    output wire [15:0] result,
    output wire [15:0] odd
    );

reg [15:0] a_reg;
reg [15:0] b_reg;
reg [31:0] tmp_a;
reg [31:0] tmp_b;
integer i;

always@(*) begin
    a_reg = A;
    b_reg = B;
end

always@(*) begin
    begin
        tmp_a = {16'b0, a_reg};
        tmp_b = {b_reg, 16'b0};
        for(i = 0;i < 16;i = i+1) begin
            tmp_a = tmp_a << 1;
            if (tmp_a >= tmp_b) begin
                tmp_a = tmp_a - tmp_b + 1;
            end
            else begin
                tmp_a = tmp_a;
            end
        end
    end
end

assign odd = tmp_a[31:16];
assign result = tmp_a[15:0];

endmodule
Result: total cell area 260.16 um2 = 1,323.3 GE.

Example 3. Top module tmu2_dpram. RTL:
// ---- file: metrex_11803.v ----

module tmu2_dpram #(
    parameter depth = 11, 
    parameter width = 32
) (
    input sys_clk,

    input [depth-1:0] ra,
    input re,
    output [width-1:0] rd,

    input [depth-1:0] wa,
    input we,
    input [width-1:0] wd
);

reg [width-1:0] ram[0:(1 << depth)-1];

reg [depth-1:0] rar;

always @(posedge sys_clk) begin
    if(re) begin
        rar <= ra;
    end
    if(we) begin
        ram[wa] <= wd;
    end
end

assign rd = ram[rar];

endmodule
Result: total cell area 102,132.74 um2 = 519,474.0 GE.

```

### power

Questions: ['power']. Designs: ['ve_Prob084_ece241_2013_q12', 'metrex_19362', 'metrex_11803']

```text
Three solved examples: three other designs, each with the exact total power after synthesis with the flow in `flow` at the clock in `clock`. The question is about the design in `rtl`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: total power 12.48 uW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles). Level: 10 uW to 100 uW.

Example 2. Top module cbc_mac_des. RTL:
// ---- file: metrex_19362.v ----
module cbc_mac_des (
  input        clk,
  input        reset,
  input        valid_i,
  input  [63:0] key_i,
  input  [63:0] data_i,
  output       valid_o,
  output [63:0] mac_o
);

  reg [63:0] iv;
  reg [63:0] key;
  reg [63:0] data;
  reg [63:0] mac;
  reg valid;
  reg [5:0] count;

  assign valid_o = valid;
  assign mac_o   = mac;

  always @(posedge clk, posedge reset) begin
    if (reset) begin
      iv     <= 64'h0;
      key    <= 64'h0;
      data   <= 64'h0;
      mac    <= 64'h0;
      valid  <= 1'b0;
      count  <= 6'd0;
    end else begin
      if (valid_i) begin
        case (count)
          6'd0: begin
            iv     <= data_i;
            key    <= key_i;
            data   <= iv ^ key;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd1: begin
            data   <= data_i ^ data;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd2: begin
            data   <= data ^ key;
            mac    <= data;
            valid  <= 1'b1;
            count  <= count + 1;
          end
          6'd3: begin
            iv     <= mac;
            key    <= key_i;
            data   <= iv ^ key;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd4: begin
            data   <= data_i ^ data;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd5: begin
            data   <= data ^ key;
            mac    <= data;
            valid  <= 1'b1;
            count  <= 6'd0;
          end
        endcase
      end
    end
  end

endmodule
Result: total power 300.8 uW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles). Level: 100 uW to 1 mW.

Example 3. Top module tmu2_dpram. RTL:
// ---- file: metrex_11803.v ----

module tmu2_dpram #(
    parameter depth = 11, 
    parameter width = 32
) (
    input sys_clk,

    input [depth-1:0] ra,
    input re,
    output [width-1:0] rd,

    input [depth-1:0] wa,
    input we,
    input [width-1:0] wd
);

reg [width-1:0] ram[0:(1 << depth)-1];

reg [depth-1:0] rar;

always @(posedge sys_clk) begin
    if(re) begin
        rar <= ra;
    end
    if(we) begin
        ram[wa] <= wd;
    end
end

assign rd = ram[rar];

endmodule
Result: total power 26.2 mW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles). Level: 10 mW or more.

```

### power (pair questions)

Questions: ['lower_power']. Designs: ['ve_Prob084_ece241_2013_q12', 'metrex_19362', 'metrex_11803']

```text
Three solved examples: three other designs, each with the exact total power after synthesis with the flow in `flow` at the clock in `clock`. The question is about the designs in `rtl_a` and `rtl_b`, not about these examples.

Example 1. Top module RefModule. RTL:
// ---- file: Prob084_ece241_2013_q12.sv ----

module RefModule (
  input clk,
  input enable,
  input S,
  input A,
  input B,
  input C,
  output reg Z
);

  reg [7:0] q;
  always @(posedge clk) begin
    if (enable)
      q <= {q[6:0], S};
  end

  assign Z = q[ {A, B, C} ];

endmodule
Result: total power 12.48 uW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles).

Example 2. Top module cbc_mac_des. RTL:
// ---- file: metrex_19362.v ----
module cbc_mac_des (
  input        clk,
  input        reset,
  input        valid_i,
  input  [63:0] key_i,
  input  [63:0] data_i,
  output       valid_o,
  output [63:0] mac_o
);

  reg [63:0] iv;
  reg [63:0] key;
  reg [63:0] data;
  reg [63:0] mac;
  reg valid;
  reg [5:0] count;

  assign valid_o = valid;
  assign mac_o   = mac;

  always @(posedge clk, posedge reset) begin
    if (reset) begin
      iv     <= 64'h0;
      key    <= 64'h0;
      data   <= 64'h0;
      mac    <= 64'h0;
      valid  <= 1'b0;
      count  <= 6'd0;
    end else begin
      if (valid_i) begin
        case (count)
          6'd0: begin
            iv     <= data_i;
            key    <= key_i;
            data   <= iv ^ key;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd1: begin
            data   <= data_i ^ data;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd2: begin
            data   <= data ^ key;
            mac    <= data;
            valid  <= 1'b1;
            count  <= count + 1;
          end
          6'd3: begin
            iv     <= mac;
            key    <= key_i;
            data   <= iv ^ key;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd4: begin
            data   <= data_i ^ data;
            valid  <= 1'b0;
            count  <= count + 1;
          end
          6'd5: begin
            data   <= data ^ key;
            mac    <= data;
            valid  <= 1'b1;
            count  <= 6'd0;
          end
        endcase
      end
    end
  end

endmodule
Result: total power 300.8 uW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles).

Example 3. Top module tmu2_dpram. RTL:
// ---- file: metrex_11803.v ----

module tmu2_dpram #(
    parameter depth = 11, 
    parameter width = 32
) (
    input sys_clk,

    input [depth-1:0] ra,
    input re,
    output [width-1:0] rd,

    input [depth-1:0] wa,
    input we,
    input [width-1:0] wd
);

reg [width-1:0] ram[0:(1 << depth)-1];

reg [depth-1:0] rar;

always @(posedge sys_clk) begin
    if(re) begin
        rar <= ra;
    end
    if(we) begin
        ram[wa] <= wd;
    end
end

assign rd = ram[rar];

endmodule
Result: total power 26.2 mW, with a generated power testbench (a new random value on each data input in every cycle, 4,000 measured cycles).

```
