# Calibrated Light


Apply a colour calibration to a light in Home Assistant. Useful for RGB strips which are more intense on particular 
RGB channels.

Currently only supports calibration via RGB color mode.

### Example Configuration 

```yaml
light:
- platform: calibrated_light
  name: "Cabinet Glow Calibrated"
  entity_id: light.cabinet_glow
  calibration_rgb: [0, -128, 0]
```
