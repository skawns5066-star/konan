package com.example.ytdownloader

import android.content.ClipboardManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.ytdownloader.databinding.ActivityMainBinding
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * 앱의 유일한 화면. 하는 일은 크게 4가지입니다.
 *  1) 앱 시작 시 다운로드 엔진(yt-dlp, FFmpeg) 준비
 *  2) 사용자가 누른 버튼(MP3/MP4)에 맞춰 다운로드 실행
 *  3) 진행률을 프로그레스 바에 표시
 *  4) 완성된 파일을 '다운로드' 폴더로 복사
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private var engineReady = false
    private var cancelled = false

    // 실행 중인 다운로드를 구분하기 위한 이름표 (취소할 때 사용)
    private val processId = "yt_download"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.pasteButton.setOnClickListener { pasteFromClipboard() }
        binding.mp3Button.setOnClickListener { startDownload(isMp3 = true) }
        binding.mp4Button.setOnClickListener { startDownload(isMp3 = false) }
        binding.cancelButton.setOnClickListener { cancelDownload() }

        handleSharedText(intent)
        initEngine()
    }

    // 유튜브 앱에서 [공유]로 링크를 보냈을 때
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleSharedText(intent)
    }

    private fun handleSharedText(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.let { binding.urlInput.setText(extractUrl(it)) }
        }
    }

    // ---------------------------------------------------------------- 1) 엔진 준비

    private fun initEngine() {
        setBusy(true)
        binding.progressBar.isIndeterminate = true
        binding.statusText.setText(R.string.status_preparing)

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                YoutubeDL.getInstance().init(application)
                FFmpeg.getInstance().init(application)
                engineReady = true
                withContext(Dispatchers.Main) {
                    binding.progressBar.isIndeterminate = false
                    binding.statusText.setText(R.string.status_idle)
                    setBusy(false)
                }
                // 유튜브는 자주 바뀌므로 yt-dlp를 최신으로 갱신 (실패해도 무시)
                runCatching { YoutubeDL.getInstance().updateYoutubeDL(application) }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.isIndeterminate = false
                    showStatus("엔진 준비 실패: ${e.message}")
                    setBusy(false)
                }
            }
        }
    }

    // ---------------------------------------------------------------- 2) 다운로드

    private fun pasteFromClipboard() {
        val clip = (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
        val text = clip?.getItemAt(0)?.coerceToText(this)?.toString()
        if (text.isNullOrBlank()) {
            Toast.makeText(this, "복사된 내용이 없습니다", Toast.LENGTH_SHORT).show()
        } else {
            binding.urlInput.setText(extractUrl(text))
        }
    }

    /** 문장 속에서 http(s):// 로 시작하는 링크만 뽑아냅니다. */
    private fun extractUrl(text: String): String =
        Regex("https?://\\S+").find(text)?.value ?: text.trim()

    private fun startDownload(isMp3: Boolean) {
        val url = extractUrl(binding.urlInput.text?.toString().orEmpty())
        if (!engineReady) {
            showStatus("아직 엔진을 준비 중입니다. 잠시 후 다시 눌러주세요.")
            return
        }
        if (!url.startsWith("http") || !(url.contains("youtube.com") || url.contains("youtu.be"))) {
            binding.urlLayout.error = "올바른 유튜브 링크를 입력해주세요"
            return
        }
        binding.urlLayout.error = null

        // 임시 작업 폴더 (앱 전용 공간). 매번 비우고 시작합니다.
        val workDir = File(cacheDir, "download").apply {
            deleteRecursively()
            mkdirs()
        }

        cancelled = false
        setBusy(true)
        binding.progressBar.progress = 0
        showStatus("다운로드 시작…")

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val request = buildRequest(url, workDir, isMp3)

                YoutubeDL.getInstance().execute(request, processId) { progress, _, _ ->
                    // 진행률(0~100)을 화면에 반영. MP4는 영상/음성을 따로 받아 바가 두 번 찰 수 있습니다.
                    runOnUiThread {
                        binding.progressBar.progress = progress.toInt().coerceIn(0, 100)
                        binding.statusText.text =
                            if (progress >= 100f) "마무리 중… (변환/합치기)" else "다운로드 중… ${progress.toInt()}%"
                    }
                }

                // 완성된 파일 찾기 → 다운로드 폴더로 복사
                val result = workDir.listFiles()
                    ?.filter { it.extension.lowercase() in listOf("mp3", "mp4") }
                    ?.maxByOrNull { it.lastModified() }
                    ?: throw IllegalStateException("결과 파일을 찾을 수 없습니다")

                saveToDownloads(result, isMp3)

                withContext(Dispatchers.Main) {
                    binding.progressBar.progress = 100
                    showStatus("완료! 다운로드 폴더에 저장됨:\n${result.name}")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    showStatus(if (cancelled) "취소되었습니다." else "실패: ${e.message}")
                }
            } finally {
                workDir.deleteRecursively()
                withContext(Dispatchers.Main) { setBusy(false) }
            }
        }
    }

    /** yt-dlp에게 전달할 '주문서'를 만듭니다. */
    private fun buildRequest(url: String, workDir: File, isMp3: Boolean): YoutubeDLRequest =
        YoutubeDLRequest(url).apply {
            addOption("--no-playlist")                       // 재생목록이 아닌 영상 1개만
            addOption("-o", "${workDir.absolutePath}/%(title).80s.%(ext)s")
            if (isMp3) {
                addOption("-x")                               // 음원만 추출
                addOption("--audio-format", "mp3")
                addOption("--audio-quality", "0")             // 최고 음질
            } else {
                addOption("-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b")
                addOption("--merge-output-format", "mp4")     // 영상+음성을 mp4 하나로
            }
        }

    // ---------------------------------------------------------------- 4) 다운로드 폴더에 저장

    /**
     * 안드로이드 10+ 에서는 MediaStore를 통해 '다운로드' 폴더에 저장합니다.
     * (이 방식은 별도의 저장소 권한이 필요 없습니다.)
     */
    private fun saveToDownloads(file: File, isMp3: Boolean) {
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, file.name)
            put(MediaStore.MediaColumns.MIME_TYPE, if (isMp3) "audio/mpeg" else "video/mp4")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        }
        val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IllegalStateException("다운로드 폴더에 파일을 만들 수 없습니다")
        contentResolver.openOutputStream(uri)?.use { out ->
            file.inputStream().use { it.copyTo(out) }
        } ?: throw IllegalStateException("파일 저장 실패")
    }

    private fun cancelDownload() {
        cancelled = true
        YoutubeDL.getInstance().destroyProcessById(processId)
    }

    // ---------------------------------------------------------------- 화면 도우미

    private fun showStatus(message: String) {
        binding.statusText.text = message
    }

    /** 다운로드 중에는 버튼을 잠그고 [취소] 버튼을 보여줍니다. */
    private fun setBusy(busy: Boolean) {
        binding.mp3Button.isEnabled = !busy
        binding.mp4Button.isEnabled = !busy
        binding.cancelButton.visibility = if (busy && engineReady) View.VISIBLE else View.GONE
    }
}
