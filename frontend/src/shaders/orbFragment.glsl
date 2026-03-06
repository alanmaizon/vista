precision highp float;

varying vec2 vUv;

uniform float uTime;
uniform vec2 uResolution;
uniform float uAudioLow;
uniform float uAudioMid;
uniform float uAudioHigh;
uniform float uOverallAmplitude;
uniform vec2 uMousePosition;
uniform vec3 uColorPalette[3];

__NOISE_GLSL__

float orbRadius() {
  return 0.9 + uAudioLow * 0.16 + uOverallAmplitude * 0.08;
}

vec3 palette(float t) {
  vec3 firstBlend = mix(uColorPalette[0], uColorPalette[1], smoothstep(0.0, 0.55, t));
  return mix(firstBlend, uColorPalette[2], smoothstep(0.42, 1.0, t));
}

float sphereSdf(vec3 p, float radius) {
  // The outer shell stays spherical, but layered noise and banding keep it organic.
  float turbulence = fbm(p * (2.2 + uAudioMid * 2.1) + vec3(0.0, uTime * 0.32, uTime * 0.18));
  float secondary = fbm(vec3(p.zxy * 3.1 + uTime * 0.24));
  float bands = sin(p.y * 8.0 + uTime * 1.3 + turbulence * 6.0) * (0.02 + uAudioMid * 0.05);
  float distort = mix(turbulence, secondary, 0.45) * (0.12 + uAudioMid * 0.16);
  float pulse = sin(uTime * 1.55 + turbulence * 7.5) * (0.03 + uAudioLow * 0.06);
  return length(p) - (radius + distort + bands + pulse);
}

float densityField(vec3 p, float radius) {
  // Interior density gives the orb its volumetric, plasma-like core.
  float shell = smoothstep(radius + 0.2, radius - 0.18, length(p));
  float flow = fbm(p * (3.4 + uAudioMid * 1.8) + vec3(uTime * 0.25, -uTime * 0.18, uTime * 0.21));
  float streaks = sin((p.y + flow) * 11.0 + uTime * 2.0) * 0.5 + 0.5;
  return shell * mix(0.18, 1.0, flow * 0.65 + streaks * 0.35);
}

vec3 estimateNormal(vec3 p, float radius) {
  vec2 epsilon = vec2(0.0015, 0.0);
  float dx = sphereSdf(p + vec3(epsilon.x, epsilon.y, epsilon.y), radius) - sphereSdf(p - vec3(epsilon.x, epsilon.y, epsilon.y), radius);
  float dy = sphereSdf(p + vec3(epsilon.y, epsilon.x, epsilon.y), radius) - sphereSdf(p - vec3(epsilon.y, epsilon.x, epsilon.y), radius);
  float dz = sphereSdf(p + vec3(epsilon.y, epsilon.y, epsilon.x), radius) - sphereSdf(p - vec3(epsilon.y, epsilon.y, epsilon.x), radius);
  return normalize(vec3(dx, dy, dz));
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution.xy) / uResolution.y;
  vec2 pointer = (uMousePosition - 0.5) * 2.0;
  float radius = orbRadius();

  vec3 ro = vec3(
    0.22 * sin(uTime * 0.21 + pointer.x * 0.55),
    0.18 * cos(uTime * 0.18 + pointer.y * 0.55),
    2.95
  );
  vec3 target = vec3(pointer * 0.12, 0.0);
  vec3 forward = normalize(target - ro);
  vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
  vec3 up = cross(forward, right);
  vec3 rd = normalize(forward * 1.85 + right * uv.x + up * uv.y);

  float t = 0.0;
  float hitT = -1.0;
  vec3 accumulated = vec3(0.0);
  float transmittance = 1.0;
  float haloDensity = 0.0;
  float sparks = 0.0;

  for (int step = 0; step < 72; step += 1) {
    vec3 pos = ro + rd * t;
    float distanceToSurface = sphereSdf(pos, radius);
    // Blend shell glow with a deeper density field during the raymarch.
    float density = exp(-abs(distanceToSurface) * mix(16.0, 9.0, uAudioMid)) * (0.04 + uOverallAmplitude * 0.05);
    float coreDensity = densityField(pos, radius) * (0.05 + uAudioLow * 0.07);
    float combinedDensity = density + coreDensity;
    float paletteIndex = clamp(
      fbm(pos * (2.9 + uAudioMid * 1.4) + vec3(0.0, uTime * 0.16, uTime * 0.23)) * 0.78 +
      uAudioHigh * 0.32,
      0.0,
      1.0
    );
    vec3 sampleColor = palette(paletteIndex);
    accumulated += sampleColor * combinedDensity * transmittance;
    transmittance *= 0.982 - uAudioHigh * 0.01;
    haloDensity += combinedDensity;

    float shellMask = smoothstep(radius + 0.14, radius - 0.08, length(pos));
    float sparkField = pow(max(0.0, valueNoise(vec3(pos.xy * 18.0, uTime * 5.2 + pos.z * 6.0)) - 0.74), 5.0);
    sparks += sparkField * shellMask * uAudioHigh * 0.55;

    if (distanceToSurface < 0.002) {
      hitT = t;
      break;
    }

    t += clamp(distanceToSurface * 0.62, 0.02, 0.11);
    if (t > 4.6) {
      break;
    }
  }

  vec3 color = vec3(0.0);
  float projection = clamp(dot(-ro, rd), 0.0, 4.5);
  vec3 closestPoint = ro + rd * projection;
  float halo = exp(-max(length(closestPoint) - radius, 0.0) * 8.5);

  vec3 bgColor = mix(
    vec3(0.01, 0.03, 0.08),
    palette(0.28 + uAudioMid * 0.25),
    smoothstep(0.85, -0.35, length(uv))
  ) * (0.18 + uOverallAmplitude * 0.1);
  color += bgColor;

  if (hitT > 0.0) {
    vec3 hitPos = ro + rd * hitT;
    vec3 normal = estimateNormal(hitPos, radius);
    vec3 lightDir = normalize(vec3(-0.45, 0.7, 0.9));
    float fresnel = pow(1.0 - max(dot(normal, -rd), 0.0), 3.0);
    float diffuse = max(dot(normal, lightDir), 0.0);
    float turbulence = fbm(hitPos * 4.2 + vec3(0.0, uTime * 0.42, uTime * 0.18));
    float shimmer = sin(turbulence * 18.0 + uTime * (8.0 + uAudioHigh * 14.0)) * 0.5 + 0.5;
    float surfaceIndex = clamp(turbulence * 0.72 + shimmer * 0.18 + uAudioMid * 0.22, 0.0, 1.0);
    vec3 surfaceColor = palette(surfaceIndex);

    // Fresnel and diffuse lighting give the shell a glassy energy-core look.
    color += surfaceColor * (0.32 + diffuse * 0.7);
    color += surfaceColor * fresnel * (1.1 + uAudioLow * 1.2);
    color += accumulated * (1.4 + uAudioMid * 0.6);
  } else {
    color += accumulated * 1.2;
  }

  color += palette(0.92) * halo * (0.34 + uAudioLow * 1.25 + haloDensity * 0.05);
  color += palette(0.68) * haloDensity * 0.055;
  color += vec3(1.0, 0.96, 1.0) * sparks * (0.55 + uAudioHigh * 0.8);

  float vignette = smoothstep(1.28, 0.16, length(uv));
  color *= vignette;

  color = color / (1.0 + color);
  color = pow(color, vec3(0.92));

  gl_FragColor = vec4(color, clamp(max(color.r, max(color.g, color.b)) * 1.35, 0.0, 1.0));
}
