package com.yurap.securedataapp

import android.annotation.SuppressLint
import android.content.Context
import com.google.android.gms.location.LocationServices
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class LocationProvider(private val context: Context) {
    @SuppressLint("MissingPermission")
    suspend fun currentLocation(): LocationData = suspendCancellableCoroutine { cont ->
        val client = LocationServices.getFusedLocationProviderClient(context)
        client.lastLocation.addOnSuccessListener { loc ->
            cont.resume(LocationData(loc?.latitude, loc?.longitude))
        }.addOnFailureListener {
            cont.resume(LocationData(null, null))
        }
    }
}
