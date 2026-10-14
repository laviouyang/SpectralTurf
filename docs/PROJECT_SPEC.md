You are my software development partner for SpectralTurf AI, a high school project for the Congressional App Challenge with a deadline of October 26, 2026.

I want you to help me build the entire working MVP described below. I am a high school student, so the code must be simple, understandable, scientifically responsible, and achievable on a short timeline. I must be able to explain every major part of the app to judges.

Do not overengineer this. Do not build a commercial-grade platform. Do not add features just because they sound impressive.

# STEP 1: Diagnose the satellite-data issue before building everything

I tested the Copernicus Request Builder and received a dark, blocky image. Changing the Evalscript did not visibly change the result, and output dimensions appeared to preserve the selected area's aspect ratio automatically.

Before implementing the complete application:

1. Explain how to verify the current request's data collection, dates, selected area, output format, and Evalscript.
2. Determine whether the image is actually a true-color Sentinel-2 product or a different layer.
3. Check whether the request uses the correct Sentinel Hub Process API configuration and endpoint for the Copernicus Data Space Ecosystem.
4. Provide a minimal, correct test request or script for true color.
5. Explain how to distinguish a successful satellite request from a request that returns technically valid but visually poor imagery.
6. Test a separate NDVI calculation and explain how to inspect the numerical results.
7. Do not assume the problem is fixed until there is evidence that the result is correct.

Use the current official documentation:
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/UserGuides/BeginnersGuide.html
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Evalscript/Functions.html
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html

The Request Builder is only a diagnostic tool. The final app must make its own real API requests through the backend.

# STEP 2: Build the MVP

## Product purpose

SpectralTurf AI helps users select a sports-field turf area, retrieve real Sentinel-2 satellite observations, calculate vegetation indices, and prioritize areas that may need human inspection.

It does not diagnose plant diseases, prove drought, prescribe watering durations, or control irrigation equipment.

## Required user workflow

1. The user opens the website.
2. The map starts in Colorado, USA.
3. The user searches for a park, school, sports complex, or address.
4. The map zooms to that place.
5. The user draws a polygon around a turf area.
6. The user can edit, clear, or redraw the polygon.
7. The user clicks an Analyze button.
8. The frontend sends the polygon coordinates and analysis options to the backend.
9. The backend requests actual Sentinel-2 data for the selected area and date range.
10. The backend calculates NDVI and NDMI using actual band values.
11. The frontend displays the results, observation date, data quality, and explanation.
12. If usable data are unavailable, the app displays an honest error or “Insufficient evidence” message.

The polygon must affect the actual satellite analysis. Do not return the same precomputed values for every location.

## Technology

Use the simplest reliable architecture:
- React frontend
- Leaflet map
- Leaflet.draw or a compatible polygon-drawing library
- Python FastAPI backend
- Copernicus Data Space Ecosystem Sentinel Hub Process API
- Open-Meteo weather API only as an optional later feature

Use a simple project structure with a frontend and backend. Avoid a database and user accounts for the MVP.

If the environment provides an existing starter project, inspect it before replacing files. Preserve useful working code.

## Map features

Implement:
- Colorado as the initial map location
- Place/address search using a geocoding service that permits the intended use
- Map zoom to search results
- Polygon drawing, editing, and deletion
- Display of the selected polygon
- Validation that the polygon is valid and large enough for meaningful analysis
- Clear feedback when no polygon is selected

Use the actual polygon geometry, preferably GeoJSON, when communicating with the backend.

Clearly explain any third-party service's usage limits or attribution requirements. Do not expose secret keys in frontend code.

## Satellite data integration

Use Sentinel-2 Level-2A data.

Relevant bands:
- B04: red, 10 m
- B08: near infrared, 10 m
- B8A: narrow near infrared, 20 m
- B11: shortwave infrared, 20 m

Calculate:

NDVI = (B08 - B04) / (B08 + B04)

NDMI = (B8A - B11) / (B8A + B11)

Handle zero denominators, invalid values, and no-data pixels safely.

Important: B8A and B11 are both 20 m bands. Do not imply NDMI has 10 m native detail. If bands need resampling for a combined output, explain the choice and do not claim that resampling creates new spatial detail.

Use a cloud and shadow masking strategy appropriate for Sentinel-2 L2A, using available scene-classification information where feasible. Check the official documentation for the correct input bands, units, and API syntax.

Use real satellite values only. Never fabricate imagery, observation dates, NDVI/NDMI results, historical observations, or weather data.

The backend should:
- Authenticate with the supported Copernicus Data Space/Sentinel Hub authentication flow.
- Read client credentials from environment variables.
- Obtain and refresh access tokens as needed.
- Make API calls from the backend only.
- Handle HTTP errors, timeouts, missing scenes, cloud contamination, and invalid responses.
- Return a useful explanation when the request fails.
- Keep secrets out of source code, frontend responses, logs, and GitHub.

First implement a simple satellite test for one known location. Then connect the selected polygon. Do not implement all API functionality at once.

## Data resolution and limitations

Sentinel-2's red and near-infrared bands have 10 m resolution; B8A and B11 have 20 m resolution.

Explain that small fields or small dry patches may not be resolved accurately. Pixels may contain mixtures of turf, dirt, pavement, shadows, and other surfaces.

For sports fields:
- Encourage the user to select only turf.
- Do not count the baseball dirt infield as grass.
- Do not assume that every pixel inside the polygon is turf.
- If a polygon is too small or has too few valid pixels, report insufficient evidence.
- Explain that satellite indices alone cannot prove drought or determine the cause of poor vegetation conditions.

## Results page

Display:
- Selected site
- Selected polygon
- Observation date
- True-color imagery if available
- NDVI layer or visualization
- NDMI layer or visualization
- Mean NDVI and NDMI for valid pixels
- Valid pixel count or proportion
- Data quality and cloud/no-data warnings
- A short explanation of the results
- Data sources and limitations

Use appropriate color scales for NDVI and NDMI, with a legend. Do not use arbitrary colors without explaining what they represent.

The index layers should come from real calculations, not a decorative mockup.

If the user changes the polygon, the next analysis must use the updated geometry.

## Explainable inspection-priority indicator

Add a simple, transparent rule-based indicator only after the real data workflow works.

The indicator should identify when an area may warrant closer inspection based on clearly described observations, such as unusually low index values relative to a suitable baseline or a meaningful change over time.

Do not invent universal thresholds and present them as scientifically validated. If no suitable baseline exists, state that the result is preliminary.

The app must not claim:
- Confirmed drought
- A proven cause of poor turf
- Exact water requirements
- Guaranteed water savings
- Validated predictive accuracy

Use wording such as “May warrant inspection” and show the reason. If evidence is inadequate, return “Insufficient evidence.”

Historical comparisons are optional. If implementing them requires too much time, leave them out and explain that the current observation is a preliminary snapshot.

## Optional weather

Only after the satellite workflow is working, consider integrating Open-Meteo to show recent precipitation and temperature. Clearly label the time period and source.

Do not let weather features delay the core satellite functionality.

## Design

Build a clean, modern, student-project-quality interface:
- Clear title and purpose
- Map as the main workspace
- Search field
- Draw/clear polygon controls
- Analyze button with loading state
- Results panel with index values and a clear legend
- Data-quality and limitations section
- Error messages that help the user recover

Keep the UI readable and responsive. Avoid excessive animations, complicated dashboards, unnecessary accounts, or decorative AI branding that distracts from the data.

## Testing and acceptance criteria

The MVP is not complete until the following are demonstrated:

1. The app starts using documented commands.
2. The user can search for a real location in Colorado.
3. The user can draw, edit, and delete a polygon.
4. The frontend sends the correct polygon coordinates to the backend.
5. The backend can retrieve real Sentinel-2 data when usable data are available and credentials/usage permissions allow it.
6. The app computes NDVI and NDMI from actual input bands.
7. The app displays the actual observation date.
8. The app reports clouds, invalid pixels, missing data, and failures honestly.
9. Different polygons trigger analyses of different areas.
10. The app does not silently replace failures with fake or hardcoded values.
11. The app explains the spatial-resolution limitations.
12. API secrets are never exposed to the frontend.
13. The README explains installation, environment variables, how to run the app, data sources, limitations, and the major code components.

Test at least three different field locations if time and data availability permit. Test a cloudy or unavailable-data case as well.

## How you should work with me

Do not dump an enormous, unexplained codebase in one response.

Work in small, complete stages:

Stage 1: Inspect the environment and diagnose the satellite-data issue.

Stage 2: Create the smallest backend endpoint that successfully requests and returns real satellite data.

Stage 3: Test NDVI and NDMI calculations.

Stage 4: Build the map and polygon-selection interface.

Stage 5: Connect the frontend to the backend.

Stage 6: Build the results interface and data-quality handling.

Stage 7: Add the inspection indicator.

Stage 8: Add optional weather, testing, documentation, and deployment if time allows.

For each stage:
- Tell me which files to create or change.
- Provide complete code for the files involved.
- Explain the important parts in beginner-friendly language.
- Give exact commands to run.
- Tell me what I should see if it works.
- Give troubleshooting steps for likely errors.
- Do not proceed as though a stage succeeded until I can verify it.

If you can directly edit files in the connected coding environment, inspect the existing files first and make the changes there. If you cannot run or test code, explicitly tell me what remains unverified.

Prioritize a working, scientifically defensible MVP over feature quantity. Keep the implementation simple enough for a high school student to explain to Congressional App Challenge judges.