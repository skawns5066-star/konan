plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.ytdownloader"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.ytdownloader"
        minSdk = 29          // Android 10 이상 (갤럭시 S25는 Android 15)
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // 갤럭시 S25(arm64) + 에뮬레이터(x86_64)만 포함해서 앱 크기를 줄입니다.
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }

    // yt-dlp / ffmpeg 실행 파일이 앱 안에서 풀려야 하므로 필요한 설정
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")

    // yt-dlp(다운로드 엔진) + FFmpeg(MP3 변환/영상 합치기)를 안드로이드용으로 포장한 라이브러리
    implementation("io.github.junkfood02.youtubedl-android:library:0.18.1")
    implementation("io.github.junkfood02.youtubedl-android:ffmpeg:0.18.1")
}
