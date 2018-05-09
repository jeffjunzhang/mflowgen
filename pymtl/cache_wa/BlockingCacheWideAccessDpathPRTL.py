#=========================================================================
# BlockingCacheWideAccessDpathPRTL.py
#=========================================================================

from pymtl      import *

# BRGTC2 custom MemMsg modified for RISC-V 32

from ifcs import MemReqMsg
from ifcs import MemReqMsg4B, MemRespMsg4B
from ifcs import MemReqMsg16B, MemRespMsg16B

#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
# LAB TASK: Include necessary files
#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''\/

from pclib.rtl            import Mux, RegEnRst
from pclib.rtl.arith      import EqComparator
from sram.SramRTL         import SramRTL

size           = 8192             # Cache size in bytes
p_opaque_nbits = 8

# local parameters not meant to be set from outside

dbw            = 32                # Short name for data bitwidth
abw            = 32                # Short name for addr bitwidth
clw            = 128               # Short name for cacheline bitwidth
nblocks        = size*8/clw        # Number of blocks in the cache
idw            = clog2(nblocks)-1  # Short name for index width
idw_off        = idw+4
o              = p_opaque_nbits

#'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''/\

class BlockingCacheWideAccessDpathPRTL( Model ):

  def __init__( s, idx_shamt = 0, CacheReqType  = MemReqMsg16B  ,
                                  CacheRespType = MemRespMsg16B ):

    #---------------------------------------------------------------------
    # Interface
    #---------------------------------------------------------------------

    # Cache request

    s.cachereq_msg       = InPort ( CacheReqType  )

    # Cache response

    s.cacheresp_msg      = OutPort( CacheRespType )

    # Memory request

    s.memreq_msg         = OutPort( MemReqMsg16B  )

    # Memory response

    s.memresp_msg        = InPort ( MemRespMsg16B )

    # control signals (ctrl->dpath)

    s.cachereq_en        = InPort( 1 )
    s.memresp_en         = InPort( 1 )
    s.is_refill          = InPort( 1 )
    s.tag_array_0_wen    = InPort( 1 )
    s.tag_array_0_ren    = InPort( 1 )
    s.tag_array_1_wen    = InPort( 1 )
    s.tag_array_1_ren    = InPort( 1 )
    s.way_sel            = InPort( 1 )
    s.way_sel_current    = InPort( 1 )
    s.data_array_wen     = InPort( 1 )
    s.data_array_ren     = InPort( 1 )
    s.skip_read_data_reg = InPort( 1 )
    s.cachereq_en        = InPort( 1 )

    # width of cacheline divided by number of bits per byte

    s.data_array_wben    = InPort( clw/8 )
    s.read_data_reg_en   = InPort( 1 )
    s.read_tag_reg_en    = InPort( 1 )
    s.read_byte_sel      = InPort( clog2(clw/8) )
    s.memreq_type        = InPort( 4 )
    s.cacheresp_type     = InPort( 4 )
    s.cacheresp_hit      = InPort( 1 )

    # Actually get all datatypes and length from types
    tmp   = CacheReqType()

    # status signals (dpath->ctrl)

    type_bw = tmp.type_.nbits
    addr_bw = tmp.addr.nbits
    opaq_bw = tmp.opaque.nbits
    data_bw = tmp.data.nbits
    len_bw  = tmp.len.nbits

    s.cachereq_data_reg_out = OutPort( data_bw )
    s.cachereq_len_reg_out  = OutPort( len_bw  )
    s.read_word_sel_mux_out = OutPort( dbw     )
    s.cachereq_type         = OutPort( type_bw )
    s.cachereq_addr         = OutPort( addr_bw )
    s.tag_match_0           = OutPort(     1   )
    s.tag_match_1           = OutPort(     1   )

    # Register the unpacked cachereq_msg

    s.cachereq_type_reg = m = RegEnRst( dtype = type_bw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.cachereq_en,
      m.in_, s.cachereq_msg.type_,
      m.out, s.cachereq_type
    )

    s.cachereq_addr_reg = m = RegEnRst( dtype = addr_bw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.cachereq_en,
      m.in_, s.cachereq_msg.addr,
      m.out, s.cachereq_addr
    )

    s.cachereq_opaque_reg = m = RegEnRst( dtype = opaq_bw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.cachereq_en,
      m.in_, s.cachereq_msg.opaque,
      m.out, s.cacheresp_msg.opaque,
    )

    s.cachereq_data_reg = m = RegEnRst( dtype = tmp.data, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.cachereq_en,
      m.in_, s.cachereq_msg.data,
      m.out, s.cachereq_data_reg_out,
    )

    s.cachereq_len_reg = m = RegEnRst( dtype = len_bw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.cachereq_en,
      m.in_, s.cachereq_msg.len,
      m.out, s.cachereq_len_reg_out,
    )

    # Register the unpacked data from memresp_msg

    s.memresp_data_reg = m = RegEnRst( dtype = clw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.memresp_en,
      m.in_, s.memresp_msg.data,
    )

    s.cachereq_tag = Wire( abw - 4 )
    s.cachereq_idx = Wire( idw )

    @s.combinational
    def comb_replicate():
      s.cachereq_tag.value = s.cachereq_addr_reg.out[4:abw]
      s.cachereq_idx.value = s.cachereq_addr_reg.out[4:idw_off]

    # Shift incoming words incase of unaligned access
    # hawajkm: I am assuming that we don't access the cache unaligned if wide-access
    s.aligned_cache_data = Wire( data_bw )

    @s.combinational
    def comb_gen_align_cl():
      s.aligned_cache_data.value = s.cachereq_data_reg_out << (s.read_byte_sel * 8)

    # Refill mux

    s.refill_mux = m = Mux( dtype = clw, nports = 2 )

    s.connect_pairs(
      m.in_[0],  s.aligned_cache_data,
      m.in_[1],  s.memresp_msg.data,
      m.sel,     s.is_refill,
    )

    # Concat

    s.temp_cachereq_tag = Wire( abw )
    s.cachereq_msg_addr = Wire( abw )
    s.cur_cachereq_idx  = Wire( idw )

    s.data_array_0_wen  = Wire(  1  )
    s.data_array_1_wen  = Wire(  1  )
    s.sram_tag_0_en     = Wire(  1  )
    s.sram_tag_1_en     = Wire(  1  )
    s.sram_data_0_en    = Wire(  1  )
    s.sram_data_1_en    = Wire(  1  )

    @s.combinational
    def comb_tag():
      s.cachereq_msg_addr.value = s.cachereq_msg.addr
      s.temp_cachereq_tag.value = concat( Bits(4, 0), s.cachereq_tag )
      if s.cachereq_en:
        s.cur_cachereq_idx.value = s.cachereq_msg_addr[4:idw_off]
      else:
        s.cur_cachereq_idx.value  = s.cachereq_idx

      # Shunning: This data_array_x_wen is built up in the same way as
      #           tag_array_x_wen. Why is this guy here, but the tag one is in ctrl?
      s.data_array_0_wen.value =  (s.data_array_wen & (s.way_sel_current == 0))
      s.data_array_1_wen.value =  (s.data_array_wen & (s.way_sel_current == 1))
      s.sram_tag_0_en.value    =  (s.tag_array_0_wen | s.tag_array_0_ren)
      s.sram_tag_1_en.value    =  (s.tag_array_1_wen | s.tag_array_1_ren)
      s.sram_data_0_en.value   =  ((s.data_array_wen & (s.way_sel_current==0)) | s.data_array_ren)
      s.sram_data_1_en.value   =  ((s.data_array_wen & (s.way_sel_current==1)) | s.data_array_ren)

    # Tag array 0

    s.tag_array_0_read_out = Wire( abw )

    s.tag_array_0 = m = SramRTL(num_bits    =  32                  ,
                                num_words   = 256                  ,
                                tech_node   = '28nm'               ,
                                module_name = 'sram_28nm_32x256_SP')

    s.connect_pairs(
      m.addr,  s.cur_cachereq_idx,
      m.out,   s.tag_array_0_read_out,
      m.we,    s.tag_array_0_wen,
      m.wmask, 0b1111,
      m.in_,   s.temp_cachereq_tag,
      m.ce,    s.sram_tag_0_en
    )

    # Tag array 1

    s.tag_array_1_read_out = Wire( abw )

    s.tag_array_1 = m = SramRTL(num_bits    =  32                  ,
                                num_words   = 256                  ,
                                tech_node   = '28nm'               ,
                                module_name = 'sram_28nm_32x256_SP')
    s.connect_pairs(
      m.addr,  s.cur_cachereq_idx,
      m.out,   s.tag_array_1_read_out,
      m.we,    s.tag_array_1_wen,
      m.wmask, 0b1111,
      m.in_,   s.temp_cachereq_tag,
      m.ce,    s.sram_tag_1_en
    )

    # Data array 0

    s.data_array_0_read_out = Wire( clw )

    s.data_array_0 = m = SramRTL(num_bits    = 128                   ,
                                 num_words   = 256                   ,
                                 tech_node   = '28nm'                ,
                                 module_name = 'sram_28nm_128x256_SP')

    s.connect_pairs(
      m.addr,  s.cur_cachereq_idx,
      m.out,   s.data_array_0_read_out,
      m.we,    s.data_array_0_wen,
      m.wmask, s.data_array_wben,
      m.in_,   s.refill_mux.out,
      m.ce,    s.sram_data_0_en
    )

    # Data array 1

    s.data_array_1_read_out = Wire( clw )

    s.data_array_1 = m = SramRTL(num_bits    = 128                   ,
                                 num_words   = 256                   ,
                                 tech_node   = '28nm'                ,
                                 module_name = 'sram_28nm_128x256_SP')

    s.connect_pairs(
      m.addr,  s.cur_cachereq_idx,
      m.out,   s.data_array_1_read_out,
      m.we,    s.data_array_1_wen,
      m.wmask, s.data_array_wben,
      m.in_,   s.refill_mux.out,
      m.ce,    s.sram_data_1_en
    )

    # Data read mux

    s.data_read_mux = m = Mux( dtype = clw, nports = 2 )

    s.connect_pairs(
      m.in_[0],  s.data_array_0_read_out,
      m.in_[1],  s.data_array_1_read_out,
      m.sel,     s.way_sel_current
    )

    # Eq comparator to check for tag matching (tag_compare_0)

    s.tag_compare_0 = m = EqComparator( nbits = abw - 4 )

    s.connect_pairs(
      m.in0, s.cachereq_tag,
      m.in1, s.tag_array_0_read_out[0:28],
      m.out, s.tag_match_0
    )

    # Eq comparator to check for tag matching (tag_compare_1)

    s.tag_compare_1 = m = EqComparator( nbits = abw - 4 )

    s.connect_pairs(
      m.in0, s.cachereq_tag,
      m.in1, s.tag_array_1_read_out[0:28],
      m.out, s.tag_match_1
    )

    # Mux that selects between the ways for requesting from memory

    s.way_sel_mux = m = Mux( dtype = abw - 4, nports = 2 )

    s.connect_pairs(
      m.in_[0],  s.tag_array_0_read_out[0:abw-4],
      m.in_[1],  s.tag_array_1_read_out[0:abw-4],
      m.sel,     s.way_sel_current
    )

    # Read data register

    s.read_data_reg = m = RegEnRst( dtype = clw, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.read_data_reg_en,
      m.in_, s.data_read_mux.out,
      m.out, s.memreq_msg.data
    )

    # Read tag register

    s.read_tag_reg = m = RegEnRst( dtype = abw - 4, reset_value = 0 )

    s.connect_pairs(
      m.en,  s.read_tag_reg_en,
      m.in_, s.way_sel_mux.out,
    )

    # Memreq Type Mux

    s.memreq_type_mux_out = Wire( abw - 4 )

    s.tag_mux = m = Mux( dtype = abw - 4, nports = 2 )

    s.connect_pairs(
      m.in_[0],  s.cachereq_tag,
      m.in_[1],  s.read_tag_reg.out,
      m.sel,     s.memreq_type[0],
      m.out,     s.memreq_type_mux_out
    )

    # Pack address for memory request

    s.memreq_addr = Wire( abw )

    @s.combinational
    def comb_addr_evict():
      s.memreq_addr.value = concat(s.memreq_type_mux_out, Bits(4, 0))

    # Skip read data reg mux

    s.read_data = Wire( clw )

    s.skip_read_data_mux = m = Mux( dtype = clw, nports = 2 )

    s.connect_pairs(
      m.in_[0],   s.read_data_reg.out,
      m.in_[1],   s.data_read_mux.out,
      m.sel,      s.skip_read_data_reg,
      m.out,      s.read_data,
    )

    s.omask        = Wire( data_bw        )
    s.output_data  = Wire( data_bw        )
    s.shft_amnt    = Wire( clog2(clw) + 1 )
    s.adjusted_len = Wire( len_bw     + 1 )

    @s.combinational
    def gen_masks():

      # Get specific word
      s.output_data .value = s.read_data
      s.adjusted_len.value = (clw / 8) if s.cachereq_len_reg_out == 0 else s.cachereq_len_reg_out

      # Mask unneeded bits
      s.shft_amnt  .value = (s.adjusted_len * 8)
      s.omask      .value = ~Bits( data_bw, 0 )
      s.omask      .value = (s.omask << s.shft_amnt)
      s.output_data.value = s.output_data >> (s.read_byte_sel * 8)
      s.output_data.value = s.output_data & ~s.omask

    @s.combinational
    def comb_addr_refill():
      if   s.cacheresp_type == MemReqMsg.TYPE_READ: s.cacheresp_msg.data.value = s.output_data
      else                                        : s.cacheresp_msg.data.value = 0

    # Taking slices of the cache request address
    #     byte offset: 2 bits wide
    #     word offset: 2 bits wide
    #     index: $clog2(nblocks) bits wide - 1 bits wide
    #     nbits: width of tag = width of addr - $clog2(nblocks) - 4
    #     entries: 256*8/128 = 16

    @s.combinational
    def comb_cacherespmsgpack():
      s.cacheresp_msg.type_.value = s.cacheresp_type
      s.cacheresp_msg.test .value = concat( Bits( 1, 0 ), s.cacheresp_hit )
      s.cacheresp_msg.len  .value = s.cachereq_len_reg_out

    @s.combinational
    def comb_memrespmsgpack():
      s.memreq_msg.type_.value    = s.memreq_type
      s.memreq_msg.opaque.value   = 0
      s.memreq_msg.addr.value     = s.memreq_addr
      s.memreq_msg.len.value      = 0