module sub_module (
    input           clk,
    input           rst_n,
    input   [7:0]   data_in,
    input           valid_in,
    output  [7:0]   data_out,
    output          valid_out,
    output          error
);
    assign data_out  = data_in;
    assign valid_out = valid_in;
    assign error     = 1'b0;
endmodule
