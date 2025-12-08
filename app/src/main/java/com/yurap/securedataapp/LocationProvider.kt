package com.yurap.securedataapp

import android.annotation.SuppressLint
import android.content.Context
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class LocationProvider(private val context: Context) {
    @SuppressLint("MissingPermission")
    suspend fun currentLocation(): LocationData = withContext(Dispatchers.IO) {
        val client = LocationServices.getFusedLocationProviderClient(context)
        suspendCancellableCoroutine<LocationData> { cont ->
            client.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, null)
                .addOnSuccessListener { loc ->
                    if (loc != null) {
                        cont.resume(LocationData(loc.latitude, loc.longitude))
                    } else {
                        client.lastLocation
                            .addOnSuccessListener { last ->
                                cont.resume(LocationData(last?.latitude, last?.longitude))
                            }
                            .addOnFailureListener { _ ->
                                cont.resume(LocationData(null, null))
                            }
                    }
                }
                .addOnFailureListener { _ ->
                    client.lastLocation
                        .addOnSuccessListener { last ->
                            cont.resume(LocationData(last?.latitude, last?.longitude))
                        }
                        .addOnFailureListener { _ ->
                            cont.resume(LocationData(null, null))
                        }
                }
        }
    }
}
