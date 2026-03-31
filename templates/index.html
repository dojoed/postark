<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PostArk</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background-color: #f5efe6;
            color: #333;
        }

        .container {
            max-width: 1100px;
            margin: auto;
            padding: 40px 20px;
        }

        /* HERO LAYOUT */
        .hero {
            display: grid;
            grid-template-columns: 1.1fr 1fr;
            gap: 50px;
            align-items: center;
        }

        /* LEFT SIDE */
        .left {
            text-align: left;
        }

        .logo {
            width: 280px; /* bigger */
            margin-bottom: 20px;
        }

        h1 {
            font-size: 34px;
            margin-bottom: 10px;
        }

        .description {
            font-size: 16px;
            line-height: 1.6;
            color: #555;
            max-width: 420px;
        }

        /* RIGHT SIDE (UPLOAD) */
        .upload-card {
            background: white;
            padding: 30px;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }

        .upload-group {
            margin-bottom: 18px;
        }

        .upload-label {
            font-weight: bold;
            margin-bottom: 6px;
            display: block;
        }

        .file-input {
            width: 100%;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #ddd;
            background: #fafafa;
        }

        .file-input:hover {
            background: #f2ebe2;
        }

        button {
            width: 100%;
            padding: 14px;
            border: none;
            background-color: #6b4f3b;
            color: white;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
        }

        button:hover {
            background-color: #5a3f2e;
        }

        /* LOADER */
        .loader {
            display: none;
            text-align: center;
            margin-top: 20px;
        }

        .spinner {
            border: 4px solid #eee;
            border-top: 4px solid #6b4f3b;
            border-radius: 50%;
            width: 36px;
            height: 36px;
            animation: spin 1s linear infinite;
            margin: auto;
        }

        @keyframes spin {
            100% { transform: rotate(360deg); }
        }

        /* RESULTS */
        .results {
            margin-top: 40px;
            background: white;
            padding: 30px;
            border-radius: 14px;
        }

        .images {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }

        .images img {
            width: 240px;
            border-radius: 10px;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .images img:hover {
            transform: scale(1.05);
        }

        .section {
            margin-bottom: 20px;
        }

        .section h3 {
            color: #6b4f3b;
            margin-bottom: 6px;
        }

        .error {
            color: red;
            margin-top: 20px;
        }

        /* MOBILE */
        @media (max-width: 768px) {
            .hero {
                grid-template-columns: 1fr;
            }

            .logo {
                width: 220px;
            }
        }
    </style>

    <script>
        function showLoader() {
            document.getElementById("loader").style.display = "block";
        }
    </script>
</head>

<body>

<div class="container">

    <div class="hero">

        <!-- LEFT -->
        <div class="left">
            <img src="/static/logo.png" class="logo">

            <h1>Bring Old Postcards Back to Life</h1>

            <p class="description">
                Upload the front and back of any postcard, and we’ll analyze it for you.
                Instantly discover who sent it, where it came from, when it was written,
                and what story it tells — all in a clear, easy-to-read format.
            </p>
        </div>

        <!-- RIGHT -->
        <div class="upload-card">
            <form method="POST" enctype="multipart/form-data" onsubmit="showLoader()">

                <div class="upload-group">
                    <label class="upload-label">Front of Postcard</label>
                    <input class="file-input" type="file" name="front" required>
                </div>

                <div class="upload-group">
                    <label class="upload-label">Back of Postcard</label>
                    <input class="file-input" type="file" name="back" required>
                </div>

                <button type="submit">Analyze Postcard</button>
            </form>

            <div id="loader" class="loader">
                <div class="spinner"></div>
                <p>Analyzing your postcard...</p>
            </div>
        </div>

    </div>

    <!-- ERROR -->
    {% if result and result.error %}
        <p class="error">{{ result.error }}</p>
    {% endif %}

    <!-- RESULTS -->
    {% if result and not result.error %}
        <div class="results">

            <div class="images">
                {% if front_path %}
                    <a href="{{ front_path }}" target="_blank">
                        <img src="{{ front_path }}">
                    </a>
                {% endif %}
                {% if back_path %}
                    <a href="{{ back_path }}" target="_blank">
                        <img src="{{ back_path }}">
                    </a>
                {% endif %}
            </div>

            <div class="section">
                <h3>Overview</h3>
                <p>{{ result.overview }}</p>
            </div>

            <div class="section">
                <h3>Analysis</h3>
                <p>{{ result.analysis }}</p>
            </div>

            <div class="section">
                <h3>Story</h3>
                <p>{{ result.story }}</p>
            </div>

            <div class="section">
                <h3>Timeline</h3>
                <p>{{ result.timeline }}</p>
            </div>

        </div>
    {% endif %}

</div>

</body>
</html>