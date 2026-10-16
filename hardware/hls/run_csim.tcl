open_project sensor_fusion_prj

set_top fusion_accelerator

add_files sensor_fusion.cpp
add_files sensor_fusion.h

add_files -tb sensor_fusion_tb.cpp

open_solution "solution1" -flow_target vivado

set_part {xc7z045ffg900-2}

create_clock -period 10 -name default

config_export -format ip_catalog \
              -output ./ip_export \
              -display_name "Sensor Fusion Accelerator" \
              -vendor "hackathon" \
              -version "1.0"

puts ""
puts "═══════════════════════════════════════════════════════════════"
puts "  Running C Simulation..."
puts "═══════════════════════════════════════════════════════════════"
puts ""

csim_design

puts ""
puts "═══════════════════════════════════════════════════════════════"
puts "  C Simulation Complete!"
puts "  Check console output for test results."
puts "═══════════════════════════════════════════════════════════════"
puts ""

exit
