+++
title = "Live ADS-B Radar"
description = "Real-time aircraft tracking from my home ADS-B receiver"
template = "radar.html"
+++

Track aircraft in real-time using data from my home-built ADS-B receiver. This feed shows planes within range of my antenna, contributing to the global flight tracking network.

## About This Setup

This radar display is powered by:
- **Receiver**: RTL-SDR dongle with a 1090 MHz antenna
- **Software**: [readsb-protobuf](https://github.com/wiedehopf/readsb-protobuf) for decoding ADS-B signals
- **Infrastructure**: Running on a Kubernetes cluster on Turing Pi

The data is fed to [ADS-B Exchange](https://adsbexchange.com) and other flight tracking networks.
