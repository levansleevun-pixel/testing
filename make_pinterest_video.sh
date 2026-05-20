#!/usr/bin/env bash
set -e

UPLOAD_DIR="/root/.claude/uploads/ab496798-84bd-4a8c-a175-f97274798aec"
OUT="/home/user/testing/pinterest_style.mp4"

# Clip durations after trim:
#   v0 (Branding)    : full ~4.93s
#   v1 (Kitchen)     : trim 0-5.5s
#   v2 (dining_1)    : trim 0-5.5s
#   v3 (dining_2)    : trim 0-5.5s
#   v4 (dining_3)    : trim 0-5.5s
# Transition: dissolve 0.8s
# xfade offsets (cumulative play time minus transition overlap):
#   xf01  = 4.93 - 0.8 = 4.13
#   xf12  = 4.13 + 5.5 - 0.8 = 8.83
#   xf23  = 8.83 + 5.5 - 0.8 = 13.53
#   xf34  = 13.53 + 5.5 - 0.8 = 18.23

ffmpeg -y \
  -i "$UPLOAD_DIR/167a51a8-Branding.mp4" \
  -i "$UPLOAD_DIR/64620c4c-Kitchen.MOV" \
  -i "$UPLOAD_DIR/c126eb66-dining_area_1.MOV" \
  -i "$UPLOAD_DIR/8ca04c89-dining_area_2.MOV" \
  -i "$UPLOAD_DIR/ab36b8e2-dining_area_3.MOV" \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,curves=r='0/0 0.5/0.56 1/1':g='0/0 0.5/0.50 1/0.97':b='0/0 0.5/0.42 1/0.85',eq=saturation=1.25:contrast=1.05:brightness=0.02,vignette=PI/3.5,setpts=PTS-STARTPTS[v0];
    [1:v]trim=0:5.5,setpts=PTS-STARTPTS,scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,curves=r='0/0 0.5/0.56 1/1':g='0/0 0.5/0.50 1/0.97':b='0/0 0.5/0.42 1/0.85',eq=saturation=1.25:contrast=1.05:brightness=0.02,vignette=PI/3.5[v1];
    [2:v]trim=0:5.5,setpts=PTS-STARTPTS,scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,curves=r='0/0 0.5/0.56 1/1':g='0/0 0.5/0.50 1/0.97':b='0/0 0.5/0.42 1/0.85',eq=saturation=1.25:contrast=1.05:brightness=0.02,vignette=PI/3.5[v2];
    [3:v]trim=0:5.5,setpts=PTS-STARTPTS,scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,curves=r='0/0 0.5/0.56 1/1':g='0/0 0.5/0.50 1/0.97':b='0/0 0.5/0.42 1/0.85',eq=saturation=1.25:contrast=1.05:brightness=0.02,vignette=PI/3.5[v3];
    [4:v]trim=0:5.5,setpts=PTS-STARTPTS,scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,curves=r='0/0 0.5/0.56 1/1':g='0/0 0.5/0.50 1/0.97':b='0/0 0.5/0.42 1/0.85',eq=saturation=1.25:contrast=1.05:brightness=0.02,vignette=PI/3.5[v4];
    [v0][v1]xfade=transition=dissolve:duration=0.8:offset=4.13[xf01];
    [xf01][v2]xfade=transition=dissolve:duration=0.8:offset=8.83[xf12];
    [xf12][v3]xfade=transition=dissolve:duration=0.8:offset=13.53[xf23];
    [xf23][v4]xfade=transition=dissolve:duration=0.8:offset=18.23[vout]
  " \
  -map "[vout]" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -r 30 \
  -an \
  "$OUT"

echo "Done: $OUT"
ffprobe -v quiet -show_format "$OUT" 2>&1 | grep duration
